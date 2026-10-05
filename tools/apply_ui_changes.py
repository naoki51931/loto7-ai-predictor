from pathlib import Path
p=Path('app/src/main/java/com/naoki51931/loto7aipredictor/MainActivity.kt');s=p.read_text(encoding='utf-8')
if 'import androidx.compose.foundation.rememberScrollState' not in s:s=s.replace('import androidx.compose.foundation.layout.*\n','import androidx.compose.foundation.layout.*\nimport androidx.compose.foundation.rememberScrollState\nimport androidx.compose.foundation.verticalScroll\n',1)
if 'import java.time.DayOfWeek' not in s:s=s.replace('import java.time.LocalDate\n','import java.time.LocalDate\nimport java.time.DayOfWeek\nimport java.time.temporal.TemporalAdjusters\n',1)
if 'import kotlin.math.abs' not in s:s=s.replace('import kotlin.math.exp\n','import kotlin.math.exp\nimport kotlin.math.abs\n',1)
if 'import kotlinx.coroutines.Dispatchers' not in s:s=s.replace('import kotlinx.coroutines.launch\n','import kotlinx.coroutines.launch\nimport kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.withContext\nimport kotlinx.coroutines.withTimeoutOrNull\n',1)
s=s.replace('private const val MODEL_TYPE_RECENCY = "RECENCY"','private const val MODEL_TYPE_RECENCY = "RECENCY"\nprivate const val MODEL_TYPE_NN = "NN_37_256_128_37"',1)
s=s.replace('Modifier.fillMaxSize().padding(padding).padding(16.dp),','Modifier.fillMaxSize().padding(padding).padding(16.dp).verticalScroll(rememberScrollState()),',1)
state='    var predictionEvaluation by remember { mutableStateOf<Evaluation?>(null) }\n'
if 'var visibleDrawCount by remember' not in s:s=s.replace(state,state+'    var visibleDrawCount by remember { mutableStateOf(100) }\n',1)
bs=s.find('                    Button(\n                        enabled = !training && modelName.isNotBlank() && draws.size >= 3,');be=s.find('\n\n                    Button(onClick = {',bs)
if bs<0 or be<0:raise SystemExit('training button not found')
button='''                    Button(enabled=!training&&modelName.isNotBlank()&&draws.size>=20,onClick={training=true;message="ニューラルネットを学習中です。最大5分かかります。";val requestedName=modelName.trim();scope.launch{val trained=withTimeoutOrNull(5*60*1000L){withContext(Dispatchers.Default){trainNeuralModel(context,requestedName,draws)}};if(trained!=null){db.modelDao().deactivateAll();db.modelDao().insert(trained.copy(active=true));models=db.modelDao().all();selectedModel=db.modelDao().active();modelName="";message="NNモデル「${trained.name}」と学習済み重みを端末に保存しました"}else message="NN学習が5分に達したため終了しました。";training=false}}){Text(if(training)"NN学習中..." else "NN学習して保存")}
                    if(training){Column(verticalArrangement=Arrangement.spacedBy(6.dp)){LinearProgressIndicator(modifier=Modifier.fillMaxWidth());Text("ニューラルネット学習中… 最大5分",style=MaterialTheme.typography.titleMedium);Text("37→256→128→37 / 80%学習・20%検証。クラッシュではありません。",style=MaterialTheme.typography.bodySmall)}}'''
s=s[:bs]+button+s[be:]
ps=s.find('private fun predictCandidates(');pe=s.find('\nprivate fun generateCandidates(',ps)
if ps<0 or pe<0:raise SystemExit('predict block not found')
predict='''private fun predictCandidates(context:android.content.Context,draws:List<Draw>,model:SavedModelEntity):Pair<List<List<Int>>,Map<Int,Double>>{if(draws.isEmpty())return emptyList<List<Int>>() to emptyMap();if(model.modelType==MODEL_TYPE_NN){val snapshot=NeuralModelStore.get(context,model.name);if(snapshot!=null){val nn=LotoNeuralNetwork();nn.restore(snapshot);val scores=nn.predict(nn.features(draws.map{it.numbers},52));return generateCandidatesFromScores(scores,5) to scores}};val scores=scoreNumbers(draws,model.lambda,model.recencyBonusWeight);return generateCandidatesFromScores(scores,5) to scores}
'''
s=s[:ps]+predict+s[pe:]
# update all call sites of pair prediction
s=s.replace('predictCandidates(recent, model)','predictCandidates(context, recent, model)')
# generateCandidates stays statistical for legacy evaluation; NN UI prediction uses persisted weights above.
marker='private fun trainModel(name: String, draws: List<Draw>): SavedModelEntity {';idx=s.find(marker)
if idx<0:raise SystemExit('train marker not found')
nntrain='''private fun trainNeuralModel(context:android.content.Context,name:String,draws:List<Draw>):SavedModelEntity{val sorted=draws.sortedBy{it.date};val split=(sorted.size*0.80).toInt().coerceIn(10,sorted.size-1);val nn=LotoNeuralNetwork();val window=52;var best=nn.snapshot();var bestAvg=Double.NEGATIVE_INFINITY;var stale=0;for(epoch in 1..80){if(Thread.currentThread().isInterrupted)break;val lr=0.012/(1.0+epoch*0.035);for(i in 1 until split){if(Thread.currentThread().isInterrupted)break;nn.trainSample(nn.features(sorted.take(i).map{it.numbers},window),sorted[i].numbers.toSet(),lr,0.00008)};var total=0.0;var cases=0;var seven=0;for(i in split until sorted.size){val scores=nn.predict(nn.features(sorted.take(i).map{it.numbers},window));val pred=scores.entries.sortedByDescending{it.value}.take(7).map{it.key}.toSet();val m=pred.intersect(sorted[i].numbers.toSet()).size;total+=m;cases++;if(m==7)seven++};val avg=if(cases==0)0.0 else total/cases;if(avg>bestAvg){bestAvg=avg;best=nn.snapshot();stale=0}else stale++;if(seven>0||stale>=10)break};nn.restore(best);NeuralModelStore.put(context,name,best);return SavedModelEntity(name=name,modelType=MODEL_TYPE_NN,lambda=0.0,recencyBonusWeight=0.0,trainedAt=LocalDate.now().toString(),active=false)}

'''
s=s[:idx]+nntrain+s[idx:]
start=s.find('private fun generateCandidatesFromScores(');end=s.find('\nprivate fun calculateMultiTicketRate(',start)
if start>=0 and end>=0:
 gen='''private fun generateCandidatesFromScores(scores:Map<Int,Double>,count:Int):List<List<Int>>{val ranked=scores.entries.sortedByDescending{it.value}.map{it.key};if(ranked.size<7)return emptyList();val out=mutableListOf<List<Int>>();for(ticket in 0 until count.coerceIn(1,5)){val anchor=ranked[(ticket*3)%minOf(15,ranked.size)];val c=mutableListOf(anchor);fun sw(n:Int)=when(abs(n-anchor)){1->2.0;2->1.5;3->1.0;4->0.65;5->0.35;else->0.0};ranked.filter{it!=anchor&&abs(it-anchor)<=5}.maxByOrNull{(scores[it]?:0.0)+sw(it)}?.let{c+=it};for(n in ranked){if(c.size>=7)break;if(n !in c)c+=n};out+=c.take(7).sorted()};return out}
''';s=s[:start]+gen+s[end:]
sm='                    draws.firstOrNull { it.date.toString() == targetDate }?.let { actual ->';em='                    Text("各口は同じ7数字セットにならないように候補を分散しています。")';a=s.find(sm);b=s.find(em,a)
if a>=0 and b>=0:
 disp='''                    Column(verticalArrangement=Arrangement.spacedBy(10.dp)){val td=runCatching{LocalDate.parse(targetDate)}.getOrNull();val friday=td?.with(TemporalAdjusters.nextOrSame(DayOfWeek.FRIDAY));val actual=friday?.let{f->draws.firstOrNull{it.date==f}};if(friday!=null){Text("当選数字 $friday",style=MaterialTheme.typography.titleLarge);if(actual!=null)NumberBalls(actual.numbers,40.dp)else Text("この週の金曜日の当選結果はまだ登録されていません。")} ;Text("予測数字 ${selectedTicketCount}口",style=MaterialTheme.typography.titleLarge);predictionCandidates.take(selectedTicketCount).forEachIndexed{i,ns->Column{Text("${i+1}口目");NumberBalls(ns,40.dp)}}}
''';s=s[:a]+disp+s[b:]
m='                Text("登録済みデータ", style = MaterialTheme.typography.titleMedium)\n';rs=s.find(m);closing='\n                }\n            }\n        }\n    }\n}\n\nprivate fun trainNeuralModel';le=s.find(closing,rs)
if rs>=0 and le>=0:
 sec='''                Text("登録済みデータ",style=MaterialTheme.typography.titleMedium)
                Text("${minOf(visibleDrawCount,draws.size)} / ${draws.size}件を表示（100件単位）")
                LazyColumn(modifier=Modifier.fillMaxWidth().height(420.dp)){items(draws.asReversed().take(visibleDrawCount)){Column{Text(it.date.toString());NumberBalls(it.numbers,38.dp)}}}
                if(visibleDrawCount<draws.size)OutlinedButton(onClick={visibleDrawCount=minOf(visibleDrawCount+100,draws.size)}){Text("次の100件をロード")}''';s=s[:rs]+sec+s[le+len('\n                }'):]
p.write_text(s,encoding='utf-8');print('Connected persistent NN weights')
