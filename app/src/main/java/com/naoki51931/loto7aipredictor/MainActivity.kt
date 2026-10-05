package com.naoki51931.loto7aipredictor

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.Color
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.room.*
import androidx.sqlite.db.SupportSQLiteDatabase
import kotlinx.coroutines.launch
import java.time.LocalDate
import kotlin.math.exp

@Entity(tableName = "draws", indices = [Index(value = ["date"], unique = true)])
data class DrawEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val date: String,
    val n1: Int, val n2: Int, val n3: Int, val n4: Int,
    val n5: Int, val n6: Int, val n7: Int
) { fun numbers() = listOf(n1, n2, n3, n4, n5, n6, n7) }

@Entity(tableName = "saved_models", indices = [Index(value = ["name"], unique = true)])
data class SavedModelEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val modelType: String,
    val lambda: Double,
    val recencyBonusWeight: Double,
    val trainedAt: String,
    val active: Boolean = false
)

@Dao
interface DrawDao {
    @Query("SELECT * FROM draws ORDER BY date ASC") suspend fun all(): List<DrawEntity>
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun insert(draw: DrawEntity)
}

@Dao
interface ModelDao {
    @Query("SELECT * FROM saved_models ORDER BY trainedAt DESC") suspend fun all(): List<SavedModelEntity>
    @Query("SELECT * FROM saved_models WHERE active = 1 LIMIT 1") suspend fun active(): SavedModelEntity?
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun insert(model: SavedModelEntity): Long
    @Query("UPDATE saved_models SET active = 0") suspend fun deactivateAll()
    @Query("UPDATE saved_models SET active = 1 WHERE id = :id") suspend fun activate(id: Long)
}

@Database(entities = [DrawEntity::class, SavedModelEntity::class], version = 2, exportSchema = false)
abstract class LotoDatabase : RoomDatabase() {
    abstract fun drawDao(): DrawDao
    abstract fun modelDao(): ModelDao
    companion object {
        @Volatile private var INSTANCE: LotoDatabase? = null
        fun get(context: android.content.Context): LotoDatabase =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext, LotoDatabase::class.java, "loto7.db"
                ).addMigrations(MIGRATION_1_2).build().also { INSTANCE = it }
            }
        private val MIGRATION_1_2 = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL(
                    "CREATE TABLE IF NOT EXISTS saved_models (" +
                        "id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, " +
                        "name TEXT NOT NULL, modelType TEXT NOT NULL, lambda REAL NOT NULL, " +
                        "recencyBonusWeight REAL NOT NULL, trainedAt TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 0)"
                )
                db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS index_saved_models_name ON saved_models(name)")
            }
        }
    }
}

private data class Draw(val date: LocalDate, val numbers: List<Int>)
private const val MODEL_TYPE_RECENCY = "RECENCY"
 
private fun numberBallColor(number: Int): Color = when (number) {
    in 1..9 -> Color(0xFF4CAF50)
    in 10..19 -> Color(0xFF2196F3)
    in 20..29 -> Color(0xFFFF9800)
    else -> Color(0xFFE53935)
}

@Composable
private fun NumberBall(number: Int, size: androidx.compose.ui.unit.Dp = 44.dp) {
    Box(
        modifier = Modifier.size(size).background(numberBallColor(number), CircleShape),
        contentAlignment = Alignment.Center
    ) {
        Text("%02d".format(number), color = Color.White, style = MaterialTheme.typography.titleMedium)
    }
}

@Composable
private fun NumberBalls(numbers: List<Int>, size: androidx.compose.ui.unit.Dp = 44.dp) {
    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        numbers.sorted().forEach { NumberBall(it, size) }
    }
}

private data class Evaluation(
    val modelName: String, val cases: Int, val averageMatches: Double,
    val hit1Rate: Double, val hit2Rate: Double, val hit3Rate: Double,
    val hit4Rate: Double, val hit5Rate: Double, val hit6Rate: Double,
    val hit7Rate: Double,
    val multiTicketRates: List<Double>,
    val olderAverage: Double, val recentAverage: Double
)

private fun evaluateModel(model: SavedModelEntity, draws: List<Draw>): Evaluation {
    val sorted = draws.sortedBy { it.date }
    val results = mutableListOf<Int>()
    for (i in 1 until sorted.size) {
        val target = sorted[i]
        val window = sorted.filter {
            it.date >= target.date.minusDays(14) && it.date < target.date
        }
        if (window.isEmpty()) continue
        val candidates = generateCandidates(window, model)
        results += candidates.first().intersect(target.numbers.toSet()).size
    }
    if (results.isEmpty()) return Evaluation(
        model.name, 0, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        List(5) { 0.0 },
        0.0, 0.0
    )
    val mid = (results.size / 2).coerceAtLeast(1)
    val older = results.take(mid)
    val recent = results.drop(mid).ifEmpty { older }
    fun rate(min: Int) = results.count { it >= min }.toDouble() / results.size * 100.0
    val multiTicketRates = (1..5).map { ticketCount ->
        calculateMultiTicketRate(model, draws, 4, ticketCount)
    }
    return Evaluation(
        model.name, results.size, results.average(),
        rate(1), rate(2), rate(3), rate(4), rate(5), rate(6), rate(7),
        multiTicketRates,
        older.average(), recent.average()
    )
}


class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { PredictorScreen(LotoDatabase.get(this)) }
    }
}

@Composable
private fun PredictorScreen(db: LotoDatabase) {
    val scope = rememberCoroutineScope()
    var targetDate by remember { mutableStateOf(LocalDate.now().toString()) }
    var drawDate by remember { mutableStateOf("") }
    var numbersText by remember { mutableStateOf("") }
    var modelName by remember { mutableStateOf("") }
    var draws by remember { mutableStateOf(listOf<Draw>()) }
    var models by remember { mutableStateOf(listOf<SavedModelEntity>()) }
    var selectedModel by remember { mutableStateOf<SavedModelEntity?>(null) }
    var prediction by remember { mutableStateOf<List<Int>>(emptyList()) }
    var predictionCandidates by remember { mutableStateOf<List<List<Int>>>(emptyList()) }
    var scores by remember { mutableStateOf<Map<Int, Double>>(emptyMap()) }
    var selectedMinMatches by remember { mutableStateOf(4) }
    var selectedTicketCount by remember { mutableStateOf(1) }
    var message by remember { mutableStateOf("抽選データを追加してください") }
    var training by remember { mutableStateOf(false) }
    var predictionEvaluation by remember { mutableStateOf<Evaluation?>(null) }

    fun refreshModels() {
        scope.launch {
            models = db.modelDao().all()
            selectedModel = db.modelDao().active() ?: models.firstOrNull()
        }
    }

    LaunchedEffect(Unit) {
        draws = db.drawDao().all().map { Draw(LocalDate.parse(it.date), it.numbers()) }
        refreshModels()
    }

    MaterialTheme {
        Scaffold(topBar = { TopAppBar(title = { Text("Loto7 AI Predictor") }) }) { padding ->
            Column(
                Modifier.fillMaxSize().padding(padding).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text("直近2週間を使い、保存したモデルを切り替えて予測")
                OutlinedTextField(
                    value = targetDate, onValueChange = { targetDate = it },
                    label = { Text("予測対象日 YYYY-MM-DD") }, modifier = Modifier.fillMaxWidth()
                )

                Text("使用モデル", style = MaterialTheme.typography.titleMedium)
                if (models.isEmpty()) {
                    Text("まだ学習済みモデルがありません。下の「学習して保存」から作成してください。")
                } else {
                    var expanded by remember { mutableStateOf(false) }
                    Box {
                        OutlinedButton(onClick = { expanded = true }) {
                            Text(selectedModel?.name ?: "モデルを選択")
                        }
                        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                            models.forEach { model ->
                                DropdownMenuItem(
                                    text = {
                                        Text(
                                            if (model.id == selectedModel?.id)
                                                "✓ ${model.name}"
                                            else model.name
                                        )
                                    },
                                    onClick = {
                                        scope.launch {
                                            db.modelDao().deactivateAll()
                                            db.modelDao().activate(model.id)
                                            selectedModel = model.copy(active = true)
                                            models = db.modelDao().all()
                                            message = "モデル「${model.name}」に切り替えました"
                                            expanded = false
                                        }
                                    }
                                )
                            }
                        }
                    }
                    selectedModel?.let {
                        Text(
                            "λ=${"%.3f".format(it.lambda)} / bonus=${"%.2f".format(it.recencyBonusWeight)} / 学習=${it.trainedAt}",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }

                OutlinedTextField(
                    value = modelName, onValueChange = { modelName = it },
                    label = { Text("新しいモデル名") },
                    placeholder = { Text("例: recency-v1") }, modifier = Modifier.fillMaxWidth()
                )

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        enabled = !training && modelName.isNotBlank() && draws.size >= 3,
                        onClick = {
                            training = true
                            message = "学習中..."
                            scope.launch {
                                val trained = trainModel(modelName.trim(), draws)
                                db.modelDao().deactivateAll()
                                db.modelDao().insert(trained.copy(active = true))
                                models = db.modelDao().all()
                                selectedModel = db.modelDao().active()
                                modelName = ""
                                training = false
                                message = "モデル「${trained.name}」を学習・保存しました"
                            }
                        }
                    ) { Text(if (training) "学習中..." else "学習して保存") }

                    Button(onClick = {
                        runCatching {
                            val date = LocalDate.parse(drawDate)
                            val ns = numbersText.split(",", " ", "、").filter { it.isNotBlank() }.map { it.toInt() }
                            require(ns.size == 7 && ns.distinct().size == 7 && ns.all { it in 1..37 })
                            scope.launch {
                                db.drawDao().insert(
                                    DrawEntity(date = date.toString(),
                                        n1 = ns[0], n2 = ns[1], n3 = ns[2], n4 = ns[3],
                                        n5 = ns[4], n6 = ns[5], n7 = ns[6])
                                )
                                draws = db.drawDao().all().map { Draw(LocalDate.parse(it.date), it.numbers()) }
                                drawDate = ""; numbersText = ""; message = "データを保存しました"
                            }
                        }.onFailure { message = "日付または7個の数字を確認してください" }
                    }) { Text("データ追加") }

                    Button(
                        enabled = selectedModel != null,
                        onClick = {
                            runCatching {
                                val target = LocalDate.parse(targetDate)
                                val recent = draws.filter {
                                    it.date >= target.minusDays(14) && it.date < target
                                }
                                val model = selectedModel!!
                                val result = predictCandidates(recent, model)
                                predictionCandidates = result.first
                                prediction = result.first.firstOrNull() ?: emptyList()
                                scores = result.second
                                predictionEvaluation = evaluateModel(model, draws)
                                message = "モデル「${model.name}」 / 使用データ: ${recent.size}回 / ${target.minusDays(14)}〜${target.minusDays(1)}"
                            }.onFailure { message = "予測対象日を確認してください" }
                        }
                    ) { Text("予測") }
                }

                Text(message)
                if (prediction.isNotEmpty()) {
                    Text("購入条件", style = MaterialTheme.typography.titleLarge)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        var matchExpanded by remember { mutableStateOf(false) }
                        Box {
                            OutlinedButton(onClick = { matchExpanded = true }) {
                                Text("${selectedMinMatches}個以上一致")
                            }
                            DropdownMenu(expanded = matchExpanded, onDismissRequest = { matchExpanded = false }) {
                                (1..7).forEach { value ->
                                    DropdownMenuItem(
                                        text = { Text(if (value == 7) "7個一致" else "${value}個以上一致") },
                                        onClick = { selectedMinMatches = value; matchExpanded = false }
                                    )
                                }
                            }
                        }
                        var ticketExpanded by remember { mutableStateOf(false) }
                        Box {
                            OutlinedButton(onClick = { ticketExpanded = true }) {
                                Text("${selectedTicketCount}口購入")
                            }
                            DropdownMenu(expanded = ticketExpanded, onDismissRequest = { ticketExpanded = false }) {
                                (1..5).forEach { value ->
                                    DropdownMenuItem(
                                        text = { Text("${value}口") },
                                        onClick = { selectedTicketCount = value; ticketExpanded = false }
                                    )
                                }
                            }
                        }
                    }
                    draws.firstOrNull { it.date.toString() == targetDate }?.let { actual ->
                        Text("当選数字", style = MaterialTheme.typography.titleLarge)
                        NumberBalls(actual.numbers, 48.dp)
                        Text("※本数字7個。ボーナス数字は含めていません。", style = MaterialTheme.typography.bodySmall)
                    }

                    Text("予測数字", style = MaterialTheme.typography.titleLarge)
                    predictionCandidates.take(selectedTicketCount).forEachIndexed { index, numbers ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("${index + 1}口目", style = MaterialTheme.typography.titleMedium)
                            Spacer(Modifier.width(8.dp))
                            NumberBalls(numbers, if (index == 0) 48.dp else 42.dp)
                        }
                    }
                    Text("各口は同じ7数字セットにならないように候補を分散しています。")
                    predictionEvaluation?.let { e ->
                        if (e.cases > 0) {
                            val selectedRate = calculateMultiTicketRate(selectedModel!!, draws, selectedMinMatches, selectedTicketCount)
                            Text("推定当選率", style = MaterialTheme.typography.titleLarge)
                            Text("%.2f%%".format(selectedRate), style = MaterialTheme.typography.displayLarge)
                            Text(
                                "少なくとも1口が" +
                                    if (selectedMinMatches == 7) "7個一致" else "${selectedMinMatches}個以上一致",
                                style = MaterialTheme.typography.titleMedium
                            )
                            Text("1口〜5口の推定率", style = MaterialTheme.typography.titleMedium)
                            (1..5).forEach { count ->
                                val rate = calculateMultiTicketRate(selectedModel!!, draws, selectedMinMatches, count)
                                Text("${count}口: %.2f%%".format(rate))
                            }
                            Text("バックテスト ${e.cases}回 / 平均一致 %.2f個".format(e.averageMatches))
                            Text("※過去データで同じ複数口予測を行った場合の実績率です。将来の当選を保証するものではありません。")
                        }
                    }
                    Text("数字別スコア", style = MaterialTheme.typography.titleMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        prediction.sorted().forEach { n -> NumberBall(n) }
                    }
                    Text("数字別スコア", style = MaterialTheme.typography.titleMedium)
                    prediction.sorted().forEach { n -> Text("%02d  %.4f".format(n, scores[n] ?: 0.0)) }
                }


                Text("モデル別バックテスト", style = MaterialTheme.typography.titleLarge)
                if (models.isNotEmpty()) {
                    models.forEach { model ->
                        var evaluation by remember(model.id) { mutableStateOf<Evaluation?>(null) }
                        OutlinedButton(onClick = {
                            evaluation = evaluateModel(model, draws)
                        }) {
                            Text("「${model.name}」の正答率を計測")
                        }
                        evaluation?.let { e ->
                            Text(
                                e.modelName + ": 平均一致 " + "%.2f".format(e.averageMatches) + "個 / " +
                                    "1個以上 " + "%.1f".format(e.hit1Rate) + "% / " +
                                    "2個以上 " + "%.1f".format(e.hit2Rate) + "% / " +
                                    "3個以上 " + "%.1f".format(e.hit3Rate) + "% / " +
                                    "4個以上（推定当選率）" + "%.1f".format(e.hit4Rate) + "%"
                            )
                            Text(
                                "5個以上 ${"%.1f".format(e.hit5Rate)}% / " +
                                    "6個以上 ${"%.1f".format(e.hit6Rate)}% / " +
                                    "7個一致 ${"%.1f".format(e.hit7Rate)}%"
                            )
                            Text(
                                "期間比較: 過去側 ${"%.2f".format(e.olderAverage)}個 → " +
                                    "最近側 ${"%.2f".format(e.recentAverage)}個 " +
                                    if (e.recentAverage > e.olderAverage) "（最近の方が高い）"
                                    else if (e.recentAverage < e.olderAverage) "（過去の方が高い）"
                                    else "（同じ）"
                            )
                        }
                    }
                }
                Text("※「推定当選率」は、予測した7個の数字から本数字が4個以上一致した割合です。ボーナス数字は現在のデータに含めていないため、賞金区分そのものの当選率ではありません。")

                Text("登録済みデータ", style = MaterialTheme.typography.titleMedium)
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    items(draws.reversed()) {
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(it.date.toString(), style = MaterialTheme.typography.titleSmall)
                            NumberBalls(it.numbers, 38.dp)
                        }
                    }
                }
            }
        }
    }
}

private fun trainModel(name: String, draws: List<Draw>): SavedModelEntity {
    val sorted = draws.sortedBy { it.date }
    val candidates = listOf(0.02, 0.05, 0.08, 0.12, 0.18, 0.25, 0.35, 0.50)
    var bestLambda = candidates.first()
    var bestScore = Double.NEGATIVE_INFINITY

    for (lambda in candidates) {
        var totalMatches = 0.0
        var cases = 0
        for (i in 1 until sorted.size) {
            val target = sorted[i]
            val window = sorted.filter {
                it.date >= target.date.minusDays(14) && it.date < target.date
            }
            if (window.isEmpty()) continue
            val result = scoreNumbers(window, lambda, 0.5)
            val predicted = result.entries.sortedByDescending { it.value }.take(7).map { it.key }.toSet()
            totalMatches += predicted.intersect(target.numbers.toSet()).size
            cases++
        }
        val average = if (cases == 0) 0.0 else totalMatches / cases
        if (average > bestScore) {
            bestScore = average
            bestLambda = lambda
        }
    }

    return SavedModelEntity(
        name = name, modelType = MODEL_TYPE_RECENCY, lambda = bestLambda,
        recencyBonusWeight = 0.5, trainedAt = LocalDate.now().toString(), active = false
    )
}

private fun predictCandidates(draws: List<Draw>, model: SavedModelEntity): Pair<List<List<Int>>, Map<Int, Double>> {
    if (draws.isEmpty()) return emptyList<List<Int>>() to emptyMap()
    val scores = scoreNumbers(draws, model.lambda, model.recencyBonusWeight)
    return generateCandidatesFromScores(scores, 5) to scores
}

private fun generateCandidates(draws: List<Draw>, model: SavedModelEntity): List<List<Int>> =
    if (draws.isEmpty()) emptyList()
    else generateCandidatesFromScores(scoreNumbers(draws, model.lambda, model.recencyBonusWeight), 5)

private fun generateCandidatesFromScores(scores: Map<Int, Double>, count: Int): List<List<Int>> {
    val base = scores.entries.sortedByDescending { it.value }
    if (base.size < 7) return emptyList()
    val maxScore = base.first().value.coerceAtLeast(1.0)
    val chosenSets = mutableListOf<List<Int>>()
    repeat(count.coerceIn(1, 5)) {
        val selected = mutableListOf<Int>()
        for (entry in base) {
            if (selected.size >= 7) break
            val overlap = chosenSets.count { entry.key in it }
            val adjusted = entry.value - overlap * maxScore * 0.18
            if (selected.isEmpty() || adjusted >= base[6].value - maxScore * 0.40) selected += entry.key
        }
        if (selected.size < 7) {
            base.filter { it.key !in selected }.take(7 - selected.size).forEach { selected += it.key }
        }
        val candidate = selected.take(7).sorted()
        if (candidate !in chosenSets) chosenSets += candidate
    }
    return chosenSets
}

private fun calculateMultiTicketRate(
    model: SavedModelEntity,
    draws: List<Draw>,
    minMatches: Int,
    ticketCount: Int
): Double {
    val sorted = draws.sortedBy { it.date }
    var cases = 0
    var success = 0
    for (i in 1 until sorted.size) {
        val target = sorted[i]
        val window = sorted.filter {
            it.date >= target.date.minusDays(14) && it.date < target.date
        }
        if (window.isEmpty()) continue
        val candidates = generateCandidates(window, model).take(ticketCount.coerceIn(1, 5))
        if (candidates.any { it.intersect(target.numbers.toSet()).size >= minMatches.coerceIn(1, 7) }) success++
        cases++
    }
    return if (cases == 0) 0.0 else success.toDouble() / cases * 100.0
}

private fun scoreNumbers(draws: List<Draw>, lambda: Double, recencyBonusWeight: Double): Map<Int, Double> {
    val sorted = draws.sortedBy { it.date }
    val latest = sorted.last().date
    val scores = mutableMapOf<Int, Double>()
    for (n in 1..37) {
        var score = 0.0
        var lastSeen: LocalDate? = null
        for (draw in sorted) {
            val age = (latest.toEpochDay() - draw.date.toEpochDay()).toDouble()
            val weight = exp(-lambda * age)
            if (n in draw.numbers) {
                score += weight
                lastSeen = draw.date
            }
        }
        val recencyBonus = lastSeen?.let {
            exp(-0.12 * (latest.toEpochDay() - it.toEpochDay()).toDouble())
        } ?: 0.0
        scores[n] = score + recencyBonus * recencyBonusWeight
    }
    return scores
}
