from pathlib import Path

p = Path('app/src/main/java/com/naoki51931/loto7aipredictor/MainActivity.kt')
s = p.read_text(encoding='utf-8')

if 'import androidx.compose.foundation.rememberScrollState' not in s:
    s = s.replace('import androidx.compose.foundation.layout.*\n', 'import androidx.compose.foundation.layout.*\nimport androidx.compose.foundation.rememberScrollState\nimport androidx.compose.foundation.verticalScroll\n', 1)
if 'import java.time.DayOfWeek' not in s:
    s = s.replace('import java.time.LocalDate\n', 'import java.time.LocalDate\nimport java.time.DayOfWeek\nimport java.time.temporal.TemporalAdjusters\n', 1)
if 'import kotlin.math.abs' not in s:
    s = s.replace('import kotlin.math.exp\n', 'import kotlin.math.exp\nimport kotlin.math.abs\n', 1)
if 'import kotlinx.coroutines.Dispatchers' not in s:
    s = s.replace('import kotlinx.coroutines.launch\n', 'import kotlinx.coroutines.launch\nimport kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.withContext\nimport kotlinx.coroutines.withTimeoutOrNull\n', 1)

s = s.replace('Modifier.fillMaxSize().padding(padding).padding(16.dp),', 'Modifier.fillMaxSize().padding(padding).padding(16.dp).verticalScroll(rememberScrollState()),', 1)
state = '    var predictionEvaluation by remember { mutableStateOf<Evaluation?>(null) }\n'
if 'var visibleDrawCount by remember' not in s:
    if state not in s: raise SystemExit('prediction state insertion point not found')
    s = s.replace(state, state + '    var visibleDrawCount by remember { mutableStateOf(100) }\n', 1)

start_marker = '                    draws.firstOrNull { it.date.toString() == targetDate }?.let { actual ->'
end_marker = '                    Text("各口は同じ7数字セットにならないように候補を分散しています。")'
a = s.find(start_marker); b = s.find(end_marker, a)
if a < 0 or b < 0: raise SystemExit('prediction display block not found')
display = '''                    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        val targetForDisplay = runCatching { LocalDate.parse(targetDate) }.getOrNull()
                        val fridayForDisplay = targetForDisplay?.with(TemporalAdjusters.nextOrSame(DayOfWeek.FRIDAY))
                        val actualForDisplay = fridayForDisplay?.let { friday -> draws.firstOrNull { it.date == friday } }
                        if (fridayForDisplay != null) {
                            Text("当選数字 ${fridayForDisplay}", style = MaterialTheme.typography.titleLarge)
                            if (actualForDisplay != null) NumberBalls(actualForDisplay.numbers, 40.dp)
                            else Text("この週の金曜日の当選結果はまだ登録されていません。", style = MaterialTheme.typography.bodyMedium)
                        } else Text("当選数字：予測対象日を確認してください", style = MaterialTheme.typography.titleLarge)
                        Text("予測数字 ${selectedTicketCount}口", style = MaterialTheme.typography.titleLarge)
                        predictionCandidates.take(selectedTicketCount).forEachIndexed { index, numbers -> Column(verticalArrangement = Arrangement.spacedBy(3.dp)) { Text("${index + 1}口目", style = MaterialTheme.typography.titleMedium); NumberBalls(numbers, 40.dp) } }
                    }
'''
s = s[:a] + display + s[b:]

button_start = s.find('                    Button(\n                        enabled = !training && modelName.isNotBlank() && draws.size >= 3,')
button_end = s.find('\n\n                    Button(onClick = {', button_start)
if button_start < 0 or button_end < 0: raise SystemExit('training button block not found')
button = '''                    Button(
                        enabled = !training && modelName.isNotBlank() && draws.size >= 3,
                        onClick = {
                            training = true
                            message = "拡張モデルを学習中です。最大5分かかります。"
                            val requestedName = modelName.trim()
                            scope.launch {
                                val trained = withTimeoutOrNull(5 * 60 * 1000L) { withContext(Dispatchers.Default) { trainModel(requestedName, draws) } }
                                if (trained != null) {
                                    db.modelDao().deactivateAll(); db.modelDao().insert(trained.copy(active = true)); models = db.modelDao().all(); selectedModel = db.modelDao().active(); modelName = ""
                                    message = "モデル「${trained.name}」を学習・保存しました（100x探索）"
                                } else message = "5分の学習時間に達したため終了しました。"
                                training = false
                            }
                        }
                    ) { Text(if (training) "学習中..." else "学習して保存") }
                    if (training) {
                        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                            Text("拡張AIモデルを学習中… 最大5分", style = MaterialTheme.typography.titleMedium)
                            Text("100倍の仮想ニューロン候補と複数パラメータを探索中。クラッシュではありません。", style = MaterialTheme.typography.bodySmall)
                        }
                    }'''
s = s[:button_start] + button + s[button_end:]

start = s.find('private fun generateCandidatesFromScores('); end = s.find('\nprivate fun calculateMultiTicketRate(', start)
if start < 0 or end < 0: raise SystemExit('candidate generator block not found')
generator = '''private fun generateCandidatesFromScores(scores: Map<Int, Double>, count: Int): List<List<Int>> {
    val ranked = scores.entries.sortedByDescending { it.value }.map { it.key }
    if (ranked.size < 7) return emptyList()
    val wanted = count.coerceIn(1, 5); val result = mutableListOf<List<Int>>()
    for (ticket in 0 until wanted) {
        val anchor = ranked[(ticket * 3) % minOf(15, ranked.size)]; val candidate = mutableListOf(anchor)
        fun spacingWeight(n: Int): Double = when (abs(n - anchor)) { 1 -> 2.0; 2 -> 1.5; 3 -> 1.0; 4 -> 0.65; 5 -> 0.35; else -> 0.0 }
        ranked.filter { it != anchor && abs(it - anchor) <= 5 }.sortedByDescending { n -> (scores[n] ?: 0.0) + spacingWeight(n) }.firstOrNull()?.let { candidate += it }
        for (n in ranked.drop(ticket)) { if (candidate.size >= 7) break; if (n in candidate) continue; val tight = candidate.count { abs(it - n) <= 2 }; val acceptance = (scores[n] ?: 0.0) - if (tight >= 2) 0.35 else 0.0; val fallback = ranked.getOrNull(6)?.let { scores[it] ?: 0.0 } ?: 0.0; if (acceptance >= fallback - 0.45 || candidate.size >= 5) candidate += n }
        for (n in ranked) { if (candidate.size >= 7) break; if (n !in candidate) candidate += n }
        result += candidate.take(7).sorted()
    }
    return result
}
'''
s = s[:start] + generator + s[end:]

old = '''        scores[n] = score + recencyBonus * recencyBonusWeight
'''
new = '''        val recentWindow = sorted.takeLast(52)
        var weightedSpacing = 0.0
        for (draw in recentWindow) if (n in draw.numbers) for (other in draw.numbers) if (other != n) weightedSpacing += when (abs(other - n)) { 1 -> 2.0; 2 -> 1.5; 3 -> 1.0; 4 -> 0.65; 5 -> 0.35; else -> 0.0 }
        val spacingBonus = if (recentWindow.isEmpty()) 0.0 else weightedSpacing / recentWindow.size * 0.12
        scores[n] = score + recencyBonus * recencyBonusWeight + spacingBonus
'''
if old not in s: raise SystemExit('score insertion point not found')
s = s.replace(old, new, 1)

ts = s.find('private fun trainModel(name: String, draws: List<Draw>): SavedModelEntity {'); te = s.find('\nprivate fun predictCandidates(', ts)
if ts < 0 or te < 0: raise SystemExit('training block not found')
training = '''private fun trainModel(name: String, draws: List<Draw>): SavedModelEntity {
    val sorted = draws.sortedBy { it.date }
    if (sorted.size < 20) return SavedModelEntity(name = name, modelType = MODEL_TYPE_RECENCY, lambda = 0.08, recencyBonusWeight = 0.5, trainedAt = LocalDate.now().toString(), active = false)
    val splitIndex = (sorted.size * 0.80).toInt().coerceIn(10, sorted.size - 1)
    val train = sorted.take(splitIndex); val validation = sorted.drop(splitIndex)
    var bestLambda = 0.08; var bestRecency = 0.5; var bestWindow = 52; var bestScore = Double.NEGATIVE_INFINITY
    val lambdas = listOf(0.003,0.005,0.008,0.012,0.018,0.025,0.035,0.05,0.07,0.10,0.14,0.20,0.28,0.40)
    val recencies = listOf(0.05,0.10,0.20,0.35,0.50,0.70,0.90,1.20,1.60,2.00)
    val windows = listOf(8,12,16,24,32,40,52,64,80,104)
    // 100x virtual-neuron ensemble: 10,000 deterministic perturbation candidates on top of the base grid.
    for (neuron in 0 until 10000) {
        if (Thread.currentThread().isInterrupted) break
        val lambdaBase = lambdas[neuron % lambdas.size]
        val recencyBase = recencies[(neuron / lambdas.size) % recencies.size]
        val window = windows[(neuron / (lambdas.size * recencies.size)) % windows.size]
        val jitter = ((neuron * 37) % 101 - 50) / 1000.0
        val lambda = (lambdaBase * (1.0 + jitter)).coerceAtLeast(0.001)
        val recency = (recencyBase * (1.0 - jitter)).coerceAtLeast(0.01)
        var total = 0.0; var hit3 = 0; var hit4 = 0; var cases = 0
        // Sample walk-forward points to make the much larger search fit the five-minute budget.
        val step = maxOf(1, train.size / 80)
        var i = maxOf(1, window)
        while (i < train.size) {
            if (Thread.currentThread().isInterrupted) break
            val target = train[i]; val history = train.take(i).takeLast(window)
            val predicted = scoreNumbers(history, lambda, recency).entries.sortedByDescending { it.value }.take(7).map { it.key }.toSet()
            val m = predicted.intersect(target.numbers.toSet()).size
            total += m; if (m >= 3) hit3++; if (m >= 4) hit4++; cases++; i += step
        }
        if (cases > 0) {
            val composite = total / cases + hit3.toDouble() / cases * 0.35 + hit4.toDouble() / cases * 1.25
            if (composite > bestScore) { bestScore = composite; bestLambda = lambda; bestRecency = recency; bestWindow = window }
        }
    }
    var validationTotal = 0.0; var validationCases = 0; var sevenHits = 0
    for (offset in validation.indices) {
        if (Thread.currentThread().isInterrupted) break
        val idx = splitIndex + offset; val target = sorted[idx]; val history = sorted.take(idx).takeLast(bestWindow)
        val predicted = scoreNumbers(history, bestLambda, bestRecency).entries.sortedByDescending { it.value }.take(7).map { it.key }.toSet()
        val m = predicted.intersect(target.numbers.toSet()).size; validationTotal += m; validationCases++; if (m == 7) sevenHits++
    }
    println("100x model: window=$bestWindow lambda=$bestLambda recency=$bestRecency validation=${if(validationCases==0)0.0 else validationTotal/validationCases} sevenHits=$sevenHits")
    return SavedModelEntity(name = name, modelType = MODEL_TYPE_RECENCY, lambda = bestLambda, recencyBonusWeight = bestRecency, trainedAt = LocalDate.now().toString(), active = false)
}
'''
s = s[:ts] + training + s[te:]

marker = '                Text("登録済みデータ", style = MaterialTheme.typography.titleMedium)\n'; rs = s.find(marker); closing = '\n                }\n            }\n        }\n    }\n}\n\nprivate fun trainModel'; le = s.find(closing, rs)
if rs < 0 or le < 0: raise SystemExit('registered data block not found')
section = '''                Text("登録済みデータ", style = MaterialTheme.typography.titleMedium)
                Text("${minOf(visibleDrawCount, draws.size)} / ${draws.size}件を表示（100件単位）", style = MaterialTheme.typography.bodySmall)
                LazyColumn(modifier = Modifier.fillMaxWidth().height(420.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) { items(draws.asReversed().take(visibleDrawCount)) { Column(verticalArrangement = Arrangement.spacedBy(4.dp)) { Text(it.date.toString(), style = MaterialTheme.typography.titleSmall); NumberBalls(it.numbers, 38.dp) } } }
                if (visibleDrawCount < draws.size) OutlinedButton(onClick = { visibleDrawCount = minOf(visibleDrawCount + 100, draws.size) }) { Text("次の100件をロード") }
                if (visibleDrawCount > 100) TextButton(onClick = { visibleDrawCount = 100 }) { Text("100件表示に戻す") }'''
s = s[:rs] + section + s[le + len('\n                }'):]
p.write_text(s, encoding='utf-8')
print('Applied expanded 100x virtual-neuron parameter search')
