from pathlib import Path

p = Path('app/src/main/java/com/naoki51931/loto7aipredictor/MainActivity.kt')
s = p.read_text(encoding='utf-8')

if 'import androidx.compose.ui.platform.LocalContext' not in s:
    s = s.replace('import androidx.compose.ui.Modifier\n', 'import androidx.compose.ui.Modifier\nimport androidx.compose.ui.platform.LocalContext\n', 1)
screen = 'private fun PredictorScreen(db: LotoDatabase) {\n'
if screen in s and '    val context = LocalContext.current\n' not in s:
    s = s.replace(screen, screen + '    val context = LocalContext.current\n', 1)

start=s.find('private fun trainNeuralModel(');end=s.find('\nprivate fun trainModel(',start)
if start<0 or end<0:raise SystemExit('generated NN trainer not found')
trainer='''private fun trainNeuralModel(context: android.content.Context, name: String, draws: List<Draw>): SavedModelEntity {
    val sorted=draws.sortedBy{it.date}; val split=(sorted.size*0.80).toInt().coerceIn(10,sorted.size-1); val nn=LotoNeuralNetwork(); val window=52
    var best=nn.snapshot(); var bestAverage=Double.NEGATIVE_INFINITY; var staleEpochs=0
    for(epoch in 1..80){ if(Thread.currentThread().isInterrupted)break; val learningRate=0.012/(1.0+epoch*0.035)
        for(i in 1 until split){if(Thread.currentThread().isInterrupted)break;nn.trainSample(nn.features(sorted.take(i).map{it.numbers},window),sorted[i].numbers.toSet(),learningRate,0.00008)}
        var total=0.0;var cases=0;var seven=0
        for(i in split until sorted.size){val scores=nn.predict(nn.features(sorted.take(i).map{it.numbers},window));val predicted=scores.entries.sortedByDescending{it.value}.take(7).map{it.key}.toSet();val m=predicted.intersect(sorted[i].numbers.toSet()).size;total+=m;cases++;if(m==7)seven++}
        val avg=if(cases==0)0.0 else total/cases;if(avg>bestAverage){bestAverage=avg;best=nn.snapshot();staleEpochs=0}else staleEpochs++;if(seven>0||staleEpochs>=10)break
    }
    nn.restore(best);NeuralModelStore.put(context,name,best);return SavedModelEntity(name=name,modelType=MODEL_TYPE_NN,lambda=0.0,recencyBonusWeight=0.0,trainedAt=LocalDate.now().toString(),active=false)
}
''';s=s[:start]+trainer+s[end:]

start=s.find('private fun predictCandidates(');end=s.find('\nprivate fun generateCandidates(',start)
if start<0 or end<0:raise SystemExit('generated prediction function not found')
predict='''private fun predictCandidates(context: android.content.Context, draws: List<Draw>, model: SavedModelEntity): Pair<List<List<Int>>, Map<Int, Double>> {
    if(draws.isEmpty())return emptyList<List<Int>>() to emptyMap()
    if(model.modelType==MODEL_TYPE_NN){NeuralModelStore.get(context,model.name)?.let{snapshot->val nn=LotoNeuralNetwork();nn.restore(snapshot);val scores=nn.predict(nn.features(draws.map{it.numbers},52));return generateCandidatesFromScores(scores,5) to scores}}
    val scores=scoreNumbers(draws,model.lambda,model.recencyBonusWeight);return generateCandidatesFromScores(scores,5) to scores
}
''';s=s[:start]+predict+s[end:]

# No forced consecutive/near-consecutive clusters. Tickets are selected only from model score ranking,
# with different rank offsets to diversify the five tickets.
start=s.find('private fun generateCandidatesFromScores(');end=s.find('\nprivate fun calculateMultiTicketRate(',start)
if start<0 or end<0:raise SystemExit('generated candidate function not found')
generator='''private fun generateCandidatesFromScores(scores: Map<Int, Double>, count: Int): List<List<Int>> {
    val ranked=scores.entries.sortedByDescending{it.value}.map{it.key}
    if(ranked.size<7)return emptyList()
    val result=mutableListOf<List<Int>>()
    val offsets=listOf(0,2,4,6,8)
    for(ticket in 0 until count.coerceIn(1,5)){
        val offset=offsets[ticket]
        val candidate=mutableListOf<Int>()
        for(step in ranked.indices){val number=ranked[(step+offset)%ranked.size];if(number !in candidate)candidate+=number;if(candidate.size==7)break}
        result+=candidate.sorted()
    }
    return result.distinct()
}

private fun predictFromLastFive(draws: List<Draw>, count: Int = 5): List<List<Int>> {
    val recent=draws.sortedByDescending{it.date}.take(5)
    if(recent.size<5)return emptyList()
    val scores=(1..37).associateWith{number->
        var score=0.0
        recent.forEachIndexed{index,draw->if(number in draw.numbers)score+=1.0+(4-index)*0.08}
        score
    }
    return generateCandidatesFromScores(scores,count)
}
''';s=s[:start]+generator+s[end:]

needle='                    Text("各口は同じ7数字セットにならないように候補を分散しています。")'
if needle in s and '直近5回だけで予測' not in s:
    insert='''                    OutlinedButton(onClick={val quick=predictFromLastFive(draws,5);if(quick.isNotEmpty()){predictionCandidates=quick;selectedTicketCount=5;message="直近5回の抽選結果だけで金曜日向け5口を予測しました"}else message="直近5回分のデータが必要です"}){Text("直近5回だけで予測")}
                    Text("出現頻度と直近重みだけを使用。連番・近接数字への加点は行いません。",style=MaterialTheme.typography.bodySmall)
''';s=s.replace(needle,needle+'\n'+insert,1)

p.write_text(s,encoding='utf-8');print('Removed consecutive-number cluster bias')
