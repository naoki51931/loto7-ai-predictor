from pathlib import Path

p = Path('app/src/main/java/com/naoki51931/loto7aipredictor/MainActivity.kt')
s = p.read_text(encoding='utf-8')

if 'import androidx.compose.foundation.rememberScrollState' not in s:
    s = s.replace('import androidx.compose.foundation.layout.*\n', 'import androidx.compose.foundation.layout.*\nimport androidx.compose.foundation.rememberScrollState\nimport androidx.compose.foundation.verticalScroll\n', 1)
if 'import java.time.DayOfWeek' not in s:
    s = s.replace('import java.time.LocalDate\n', 'import java.time.LocalDate\nimport java.time.DayOfWeek\nimport java.time.temporal.TemporalAdjusters\n', 1)
if 'import kotlin.math.abs' not in s:
    s = s.replace('import kotlin.math.exp\n', 'import kotlin.math.exp\nimport kotlin.math.abs\n', 1)

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
                        predictionCandidates.take(selectedTicketCount).forEachIndexed { index, numbers ->
                            Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                Text("${index + 1}口目", style = MaterialTheme.typography.titleMedium)
                                NumberBalls(numbers, 40.dp)
                            }
                        }
                    }
'''
s = s[:a] + display + s[b:]

start = s.find('private fun generateCandidatesFromScores('); end = s.find('\nprivate fun calculateMultiTicketRate(', start)
if start < 0 or end < 0: raise SystemExit('candidate generator block not found')
generator = '''private fun generateCandidatesFromScores(scores: Map<Int, Double>, count: Int): List<List<Int>> {
    val ranked = scores.entries.sortedByDescending { it.value }.map { it.key }
    if (ranked.size < 7) return emptyList()
    val wanted = count.coerceIn(1, 5)
    val result = mutableListOf<List<Int>>()
    for (ticket in 0 until wanted) {
        val anchor = ranked[(ticket * 3) % minOf(15, ranked.size)]
        val candidate = mutableListOf(anchor)
        val nearby = ranked.filter { it != anchor && abs(it - anchor) <= 5 }
            .sortedBy { n -> abs(n - anchor) * 0.70 - (scores[n] ?: 0.0) * 0.30 }

        // Every ticket is pair-first: one anchor plus one nearby high-score number.
        for (n in nearby) {
            if (candidate.size >= 2) break
            if (n !in candidate) candidate += n
        }

        // Fill remaining positions from high-score numbers and avoid forcing a triple cluster.
        for (n in ranked.drop(ticket)) {
            if (candidate.size >= 7) break
            if (n in candidate) continue
            val wouldMakeTriple = candidate.count { abs(it - n) <= 2 } >= 2
            if (!wouldMakeTriple || candidate.size >= 6) candidate += n
        }
        for (n in ranked) {
            if (candidate.size >= 7) break
            if (n !in candidate) candidate += n
        }
        result += candidate.take(7).sorted()
    }
    return result
}
'''
s = s[:start] + generator + s[end:]

old = '''        scores[n] = score + recencyBonus * recencyBonusWeight
'''
new = '''        val recentWindow = sorted.takeLast(52)
        var neighborHits = 0.0
        var pairStrength = 0.0
        for (draw in recentWindow) {
            if (n in draw.numbers) neighborHits += draw.numbers.count { other -> other != n && abs(other - n) <= 4 }
            pairStrength += draw.numbers.count { other -> abs(other - n) <= 2 }.toDouble() * 0.02
        }
        val clusterBonus = if (recentWindow.isEmpty()) 0.0 else neighborHits / recentWindow.size * 0.22
        scores[n] = score + recencyBonus * recencyBonusWeight + clusterBonus + pairStrength
'''
if old not in s: raise SystemExit('score insertion point not found')
s = s.replace(old, new, 1)

marker = '                Text("登録済みデータ", style = MaterialTheme.typography.titleMedium)\n'; rs = s.find(marker)
closing = '\n                }\n            }\n        }\n    }\n}\n\nprivate fun trainModel'; le = s.find(closing, rs)
if rs < 0 or le < 0: raise SystemExit('registered data block not found')
section = '''                Text("登録済みデータ", style = MaterialTheme.typography.titleMedium)
                Text("${minOf(visibleDrawCount, draws.size)} / ${draws.size}件を表示（100件単位）", style = MaterialTheme.typography.bodySmall)
                LazyColumn(modifier = Modifier.fillMaxWidth().height(420.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(draws.asReversed().take(visibleDrawCount)) {
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) { Text(it.date.toString(), style = MaterialTheme.typography.titleSmall); NumberBalls(it.numbers, 38.dp) }
                    }
                }
                if (visibleDrawCount < draws.size) OutlinedButton(onClick = { visibleDrawCount = minOf(visibleDrawCount + 100, draws.size) }) { Text("次の100件をロード") }
                if (visibleDrawCount > 100) TextButton(onClick = { visibleDrawCount = 100 }) { Text("100件表示に戻す") }'''
s = s[:rs] + section + s[le + len('\n                }'):]
p.write_text(s, encoding='utf-8')
print('Applied pair-first prediction model to all tickets')
