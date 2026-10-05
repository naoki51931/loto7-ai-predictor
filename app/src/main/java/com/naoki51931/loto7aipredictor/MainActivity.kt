package com.naoki51931.loto7aipredictor

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.room.*
import kotlinx.coroutines.launch
import java.time.LocalDate
import kotlin.math.exp

@Entity(tableName = "draws", indices = [Index(value = ["date"], unique = true)])
data class DrawEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val date: String,
    val n1: Int, val n2: Int, val n3: Int, val n4: Int,
    val n5: Int, val n6: Int, val n7: Int
) {
    fun numbers() = listOf(n1, n2, n3, n4, n5, n6, n7)
}

@Dao
interface DrawDao {
    @Query("SELECT * FROM draws ORDER BY date ASC")
    suspend fun all(): List<DrawEntity>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(draw: DrawEntity)
}

@Database(entities = [DrawEntity::class], version = 1, exportSchema = false)
abstract class LotoDatabase : RoomDatabase() {
    abstract fun drawDao(): DrawDao

    companion object {
        @Volatile private var INSTANCE: LotoDatabase? = null
        fun get(context: android.content.Context): LotoDatabase =
            INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext, LotoDatabase::class.java, "loto7.db"
                ).build().also { INSTANCE = it }
            }
    }
}

private data class Draw(val date: LocalDate, val numbers: List<Int>)

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
    var draws by remember { mutableStateOf(listOf<Draw>()) }
    var prediction by remember { mutableStateOf<List<Int>>(emptyList()) }
    var scores by remember { mutableStateOf<Map<Int, Double>>(emptyMap()) }
    var message by remember { mutableStateOf("抽選データを追加してください") }

    LaunchedEffect(Unit) {
        draws = db.drawDao().all().map { Draw(LocalDate.parse(it.date), it.numbers()) }
    }

    MaterialTheme {
        Scaffold(
            topBar = { TopAppBar(title = { Text("Loto7 AI Predictor") }) }
        ) { padding ->
            Column(
                Modifier.fillMaxSize().padding(padding).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                Text("直近2週間を重視して次回の7数字を予測")
                OutlinedTextField(
                    value = targetDate, onValueChange = { targetDate = it },
                    label = { Text("予測対象日 YYYY-MM-DD") },
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = drawDate, onValueChange = { drawDate = it },
                    label = { Text("抽選日 YYYY-MM-DD") },
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = numbersText, onValueChange = { numbersText = it },
                    label = { Text("7数字 例: 1,5,8,12,20,31,37") },
                    modifier = Modifier.fillMaxWidth()
                )

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = {
                        runCatching {
                            val date = LocalDate.parse(drawDate)
                            val ns = numbersText.split(",", " ", "、")
                                .filter { it.isNotBlank() }.map { it.toInt() }
                            require(ns.size == 7 && ns.distinct().size == 7 && ns.all { it in 1..37 })
                            scope.launch {
                                db.drawDao().insert(
                                    DrawEntity(
                                        date = date.toString(),
                                        n1 = ns[0], n2 = ns[1], n3 = ns[2], n4 = ns[3],
                                        n5 = ns[4], n6 = ns[5], n7 = ns[6]
                                    )
                                )
                                draws = db.drawDao().all().map {
                                    Draw(LocalDate.parse(it.date), it.numbers())
                                }
                                drawDate = ""
                                numbersText = ""
                                message = "データを保存しました"
                            }
                        }.onFailure { message = "日付または7個の数字を確認してください" }
                    }) { Text("データ追加") }

                    Button(onClick = {
                        runCatching {
                            val target = LocalDate.parse(targetDate)
                            val recent = draws.filter {
                                it.date >= target.minusDays(14) && it.date < target
                            }
                            val result = predict(recent)
                            prediction = result.first
                            scores = result.second
                            message = "使用データ: ${recent.size}回 / __DOLLAR__{target.minusDays(14)}〜__DOLLAR__{target.minusDays(1)}"
                        }.onFailure {
                            message = "予測対象日を確認してください"
                        }
                    }) { Text("予測") }
                }

                Text(message)

                if (prediction.isNotEmpty()) {
                    Text("予測数字", style = MaterialTheme.typography.titleLarge)
                    Text(
                        prediction.joinToString("  ") { "%02d".format(it) },
                        style = MaterialTheme.typography.headlineSmall
                    )
                    Text("最近の抽選ほど指数的に高い重みを付けています。日付そのものはモデル入力に使用しません。")
                    Text("数字別スコア", style = MaterialTheme.typography.titleMedium)
                    prediction.forEach { n ->
                        Text("%02d  %.4f".format(n, scores[n] ?: 0.0))
                    }
                }

                Text("登録済みデータ", style = MaterialTheme.typography.titleMedium)
                LazyColumn(
                    modifier = Modifier.fillMaxWidth().weight(1f),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    items(draws.reversed()) {
                        Text("__DOLLAR__{it.date}: __DOLLAR__{it.numbers.joinToString(", ")}")
                    }
                }
            }
        }
    }
}

private fun predict(draws: List<Draw>): Pair<List<Int>, Map<Int, Double>> {
    if (draws.isEmpty()) return emptyList<Int>() to emptyMap()

    val sorted = draws.sortedBy { it.date }
    val latest = sorted.last().date
    val scores = mutableMapOf<Int, Double>()

    for (n in 1..37) {
        var score = 0.0
        var lastSeen: LocalDate? = null
        for (draw in sorted) {
            val age = (latest.toEpochDay() - draw.date.toEpochDay()).toDouble()
            val weight = exp(-0.18 * age)
            if (n in draw.numbers) {
                score += weight
                lastSeen = draw.date
            }
        }
        val recencyBonus = lastSeen?.let {
            exp(-0.12 * (latest.toEpochDay() - it.toEpochDay()).toDouble())
        } ?: 0.0
        scores[n] = score + recencyBonus * 0.5
    }

    val selected = scores.entries.sortedByDescending { it.value }
        .take(7).map { it.key }.sorted()
    return selected to scores
}
