from pathlib import Path

p = Path('app/src/main/java/com/naoki51931/loto7aipredictor/MainActivity.kt')
s = p.read_text(encoding='utf-8')

if 'import androidx.compose.ui.platform.LocalContext' not in s:
    s = s.replace('import androidx.compose.ui.Modifier\n', 'import androidx.compose.ui.Modifier\nimport androidx.compose.ui.platform.LocalContext\n', 1)

screen = 'private fun PredictorScreen(db: LotoDatabase) {\n'
if screen in s and '    val context = LocalContext.current\n' not in s:
    s = s.replace(screen, screen + '    val context = LocalContext.current\n', 1)

start = s.find('private fun trainNeuralModel(')
end = s.find('\nprivate fun trainModel(', start)
if start < 0 or end < 0:
    raise SystemExit('generated NN trainer not found')
trainer = '''private fun trainNeuralModel(
    context: android.content.Context,
    name: String,
    draws: List<Draw>
): SavedModelEntity {
    val sorted = draws.sortedBy { it.date }
    val split = (sorted.size * 0.80).toInt().coerceIn(10, sorted.size - 1)
    val nn = LotoNeuralNetwork()
    val window = 52
    var best = nn.snapshot()
    var bestAverage = Double.NEGATIVE_INFINITY
    var staleEpochs = 0
    for (epoch in 1..80) {
        if (Thread.currentThread().isInterrupted) break
        val learningRate = 0.012 / (1.0 + epoch * 0.035)
        for (i in 1 until split) {
            if (Thread.currentThread().isInterrupted) break
            nn.trainSample(nn.features(sorted.take(i).map { it.numbers }, window), sorted[i].numbers.toSet(), learningRate, 0.00008)
        }
        var totalMatches = 0.0
        var cases = 0
        var sevenHits = 0
        for (i in split until sorted.size) {
            val scores = nn.predict(nn.features(sorted.take(i).map { it.numbers }, window))
            val predicted = scores.entries.sortedByDescending { it.value }.take(7).map { it.key }.toSet()
            val matches = predicted.intersect(sorted[i].numbers.toSet()).size
            totalMatches += matches
            cases++
            if (matches == 7) sevenHits++
        }
        val average = if (cases == 0) 0.0 else totalMatches / cases
        if (average > bestAverage) {
            bestAverage = average
            best = nn.snapshot()
            staleEpochs = 0
        } else staleEpochs++
        if (sevenHits > 0 || staleEpochs >= 10) break
    }
    nn.restore(best)
    NeuralModelStore.put(context, name, best)
    return SavedModelEntity(name = name, modelType = MODEL_TYPE_NN, lambda = 0.0, recencyBonusWeight = 0.0, trainedAt = LocalDate.now().toString(), active = false)
}
'''
s = s[:start] + trainer + s[end:]

start = s.find('private fun predictCandidates(')
end = s.find('\nprivate fun generateCandidates(', start)
if start < 0 or end < 0:
    raise SystemExit('generated prediction function not found')
predict = '''private fun predictCandidates(
    context: android.content.Context,
    draws: List<Draw>,
    model: SavedModelEntity
): Pair<List<List<Int>>, Map<Int, Double>> {
    if (draws.isEmpty()) return emptyList<List<Int>>() to emptyMap()
    if (model.modelType == MODEL_TYPE_NN) {
        val snapshot = NeuralModelStore.get(context, model.name)
        if (snapshot != null) {
            val nn = LotoNeuralNetwork()
            nn.restore(snapshot)
            val nnScores = nn.predict(nn.features(draws.map { it.numbers }, 52))
            return generateCandidatesFromScores(nnScores, 5) to nnScores
        }
    }
    val scores = scoreNumbers(draws, model.lambda, model.recencyBonusWeight)
    return generateCandidatesFromScores(scores, 5) to scores
}
'''
s = s[:start] + predict + s[end:]

# apply_ui_changes.py also emits this function as one compressed line. Replace it too.
start = s.find('private fun generateCandidatesFromScores(')
end = s.find('\nprivate fun calculateMultiTicketRate(', start)
if start < 0 or end < 0:
    raise SystemExit('generated candidate function not found')
generator = '''private fun generateCandidatesFromScores(
    scores: Map<Int, Double>,
    count: Int
): List<List<Int>> {
    val ranked = scores.entries.sortedByDescending { it.value }.map { it.key }
    if (ranked.size < 7) return emptyList()
    val result = mutableListOf<List<Int>>()
    for (ticket in 0 until count.coerceIn(1, 5)) {
        val anchor = ranked[(ticket * 3) % minOf(15, ranked.size)]
        val candidate = mutableListOf(anchor)
        fun spacingWeight(number: Int): Double = when (abs(number - anchor)) {
            1 -> 2.0
            2 -> 1.5
            3 -> 1.0
            4 -> 0.65
            5 -> 0.35
            else -> 0.0
        }
        ranked
            .filter { it != anchor && abs(it - anchor) <= 5 }
            .maxByOrNull { number -> (scores[number] ?: 0.0) + spacingWeight(number) }
            ?.let { candidate += it }
        for (number in ranked) {
            if (candidate.size >= 7) break
            if (number !in candidate) candidate += number
        }
        result += candidate.take(7).sorted()
    }
    return result
}
'''
s = s[:start] + generator + s[end:]

p.write_text(s, encoding='utf-8')
print('Fixed generated NN and candidate Kotlin syntax')
