package com.naoki51931.loto7aipredictor

import kotlin.math.exp
import kotlin.math.sqrt
import kotlin.random.Random

/**
 * Small on-device MLP for Loto7 ranking.
 * Input: 37 number frequencies over a recent history window.
 * Hidden layers: 256 -> 128 ReLU neurons.
 * Output: 37 independent sigmoid probabilities.
 *
 * This is intentionally dependency-free so the Android APK can train offline.
 */
data class NeuralNetworkResult(
    val probabilities: Map<Int, Double>,
    val validationAverage: Double,
    val validationSevenHits: Int,
    val epochs: Int
)

class LotoNeuralNetwork(
    private val inputSize: Int = 37,
    private val hidden1: Int = 256,
    private val hidden2: Int = 128,
    private val outputSize: Int = 37,
    seed: Int = 51931
) {
    private val random = Random(seed)
    private val w1 = Array(hidden1) { DoubleArray(inputSize) { init(inputSize) } }
    private val b1 = DoubleArray(hidden1)
    private val w2 = Array(hidden2) { DoubleArray(hidden1) { init(hidden1) } }
    private val b2 = DoubleArray(hidden2)
    private val w3 = Array(outputSize) { DoubleArray(hidden2) { init(hidden2) } }
    private val b3 = DoubleArray(outputSize)

    private fun init(fanIn: Int) = (random.nextDouble() * 2.0 - 1.0) * sqrt(2.0 / fanIn)
    private fun relu(x: Double) = if (x > 0.0) x else 0.0
    private fun sigmoid(x: Double): Double {
        val z = x.coerceIn(-30.0, 30.0)
        return 1.0 / (1.0 + exp(-z))
    }

    fun features(history: List<List<Int>>, window: Int): DoubleArray {
        val selected = history.takeLast(window)
        val x = DoubleArray(inputSize)
        if (selected.isEmpty()) return x
        selected.forEachIndexed { index, numbers ->
            val age = selected.size - 1 - index
            val recency = exp(-age / 16.0)
            numbers.forEach { n -> if (n in 1..37) x[n - 1] += recency }
        }
        val max = x.maxOrNull()?.coerceAtLeast(1e-9) ?: 1.0
        for (i in x.indices) x[i] /= max
        return x
    }

    private data class Forward(val x: DoubleArray, val z1: DoubleArray, val h1: DoubleArray, val z2: DoubleArray, val h2: DoubleArray, val y: DoubleArray)

    private fun forward(x: DoubleArray): Forward {
        val z1 = DoubleArray(hidden1) { j -> b1[j] + w1[j].indices.sumOf { i -> w1[j][i] * x[i] } }
        val h1 = DoubleArray(hidden1) { relu(z1[it]) }
        val z2 = DoubleArray(hidden2) { j -> b2[j] + w2[j].indices.sumOf { i -> w2[j][i] * h1[i] } }
        val h2 = DoubleArray(hidden2) { relu(z2[it]) }
        val y = DoubleArray(outputSize) { j -> sigmoid(b3[j] + w3[j].indices.sumOf { i -> w3[j][i] * h2[i] }) }
        return Forward(x, z1, h1, z2, h2, y)
    }

    fun trainSample(x: DoubleArray, winning: Set<Int>, learningRate: Double, l2: Double) {
        val f = forward(x)
        val d3 = DoubleArray(outputSize) { j -> f.y[j] - if ((j + 1) in winning) 1.0 else 0.0 }
        val d2 = DoubleArray(hidden2) { i ->
            var sum = 0.0
            for (j in 0 until outputSize) sum += w3[j][i] * d3[j]
            if (f.z2[i] > 0.0) sum else 0.0
        }
        val d1 = DoubleArray(hidden1) { i ->
            var sum = 0.0
            for (j in 0 until hidden2) sum += w2[j][i] * d2[j]
            if (f.z1[i] > 0.0) sum else 0.0
        }
        for (j in 0 until outputSize) {
            for (i in 0 until hidden2) w3[j][i] -= learningRate * (d3[j] * f.h2[i] + l2 * w3[j][i])
            b3[j] -= learningRate * d3[j]
        }
        for (j in 0 until hidden2) {
            for (i in 0 until hidden1) w2[j][i] -= learningRate * (d2[j] * f.h1[i] + l2 * w2[j][i])
            b2[j] -= learningRate * d2[j]
        }
        for (j in 0 until hidden1) {
            for (i in 0 until inputSize) w1[j][i] -= learningRate * (d1[j] * f.x[i] + l2 * w1[j][i])
            b1[j] -= learningRate * d1[j]
        }
    }

    fun predict(x: DoubleArray): Map<Int, Double> = forward(x).y.mapIndexed { index, value -> index + 1 to value }.toMap()
}
