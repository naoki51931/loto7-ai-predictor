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
import java.time.LocalDate

private data class Draw(val date: LocalDate, val numbers: List<Int>)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { PredictorScreen() }
    }
}

@Composable
private fun PredictorScreen() {
    var targetDate by remember { mutableStateOf(LocalDate.now().toString()) }
    var drawDate by remember { mutableStateOf("") }
    var numbersText by remember { mutableStateOf("") }
    var draws by remember { mutableStateOf(listOf<Draw>()) }
    var prediction by remember { mutableStateOf<List<Int>>(emptyList()) }
    var message by remember { mutableStateOf("予測対象日の2週間前〜直前のデータだけを使用します") }

    MaterialTheme {
        Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("Loto7 AI Predictor", style = MaterialTheme.typography.headlineMedium)
            Text("直近2週間の抽選データだけで次回を予測")
            OutlinedTextField(targetDate, { targetDate = it }, label = { Text("予測対象日 YYYY-MM-DD") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(drawDate, { drawDate = it }, label = { Text("抽選日 YYYY-MM-DD") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(numbersText, { numbersText = it }, label = { Text("7数字: 1,5,8,12,20,31,37") }, modifier = Modifier.fillMaxWidth())
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    runCatching {
                        val d = LocalDate.parse(drawDate)
                        val ns = numbersText.split(",", " ").filter { it.isNotBlank() }.map { it.toInt() }
                        require(ns.size == 7 && ns.distinct().size == 7 && ns.all { it in 1..37 })
                        draws = (draws + Draw(d, ns)).distinctBy { it.date }.sortedBy { it.date }
                        drawDate = ""; numbersText = ""
                        message = "データを追加しました"
                    }.onFailure { message = "日付または7個の数字を確認してください" }
                }) { Text("データ追加") }
                Button(onClick = {
                    runCatching {
                        val target = LocalDate.parse(targetDate)
                        val recent = draws.filter { it.date >= target.minusDays(14) && it.date < target }
                        prediction = predict(recent)
                        message = "使用データ: ${recent.size}回 / ${target.minusDays(14)}〜${target.minusDays(1)}"
                    }.onFailure { message = "予測対象日を確認してください" }
                }) { Text("予測") }
            }
            Text(message)
            if (prediction.isNotEmpty()) {
                Text("予測数字", style = MaterialTheme.typography.titleLarge)
                Text(prediction.joinToString("  ") { "%02d".format(it) }, style = MaterialTheme.typography.headlineSmall)
                Text("日付そのものは予測モデルの入力には使用していません")
            }
            Text("登録済みデータ", style = MaterialTheme.typography.titleMedium)
            LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                items(draws) { Text("${it.date}: ${it.numbers.joinToString(", ")}") }
            }
        }
    }
}

private fun predict(draws: List<Draw>): List<Int> {
    if (draws.isEmpty()) return emptyList()
    val frequency = IntArray(38)
    val lastSeen = LongArray(38) { Long.MIN_VALUE }
    draws.sortedBy { it.date }.forEach { draw -> draw.numbers.forEach { n -> frequency[n]++; lastSeen[n] = draw.date.toEpochDay() } }
    val latest = draws.maxOf { it.date.toEpochDay() }
    return (1..37).sortedByDescending { n -> frequency[n] * 3.0 + if (lastSeen[n] == Long.MIN_VALUE) 0.0 else (latest - lastSeen[n]).coerceAtMost(14) * 0.2 }.take(7).sorted()
}
