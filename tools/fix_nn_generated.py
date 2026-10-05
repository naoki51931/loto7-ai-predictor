from pathlib import Path

p = Path('app/src/main/java/com/naoki51931/loto7aipredictor/MainActivity.kt')
s = p.read_text(encoding='utf-8')

# The generated NN code used compressed one-line Kotlin. Rewrite it as normal Kotlin
# so KSP/Kotlin parsing is deterministic and provide the Compose Context it needs.
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
            val history = sorted.take(i).map { it.numbers }
            nn.trainSample(
                nn.features(history, window),
                sorted[i].numbers.toSet(),
                learningRate,
                0.00008
            )
        }

        var totalMatches = 0.0
        var cases = 0
        var sevenHits = 0
        for (i in split until sorted.size) {
            val history = sorted.take(i).map { it.numbers }
            val scores = nn.predict(nn.features(history, window))
            val predicted = scores.entries
                .sortedByDescending { it.value }
                .take(7)
                .map { it.key }
                .toSet()
            val matches = predicted.intersect(sorted[i].numbers.toSet()).size
            totalMatches += matches
            cases += 1
            if (matches == 7) sevenHits += 1
        }

        val average = if (cases == 0) 0.0 else totalMatches / cases
        if (average > bestAverage) {
            bestAverage = average
            best = nn.snapshot()
            staleEpochs = 0
        } else {
            staleEpochs += 1
        }
        if (sevenHits > 0 || staleEpochs >= 10) break
    }

    nn.restore(best)
    NeuralModelStore.put(context, name, best)
    return SavedModelEntity(
        name = name,
        modelType = MODEL_TYPE_NN,
        lambda = 0.0,
        recencyBonusWeight = 0.0,
        trainedAt = LocalDate.now().toString(),
        active = false
    )
}
'''
s = s[:start] + trainer + s[end:]

# Also expand the generated prediction function to avoid parser ambiguity.
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

p.write_text(s, encoding='utf-8')
print('Fixed generated NN Kotlin syntax and context wiring')
