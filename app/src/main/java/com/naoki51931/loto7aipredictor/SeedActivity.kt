package com.naoki51931.loto7aipredictor

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import java.io.BufferedReader
import java.io.InputStreamReader
import java.util.concurrent.Executors

/**
 * Seeds the Room database from the Loto7 history bundled into the APK.
 * The CSV is generated from Mizuho Bank's published per-draw CSV files during CI.
 */
class SeedActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Executors.newSingleThreadExecutor().execute {
            try {
                seedBundledDraws()
            } finally {
                runOnUiThread {
                    startActivity(Intent(this, MainActivity::class.java))
                    finish()
                }
            }
        }
    }

    private fun seedBundledDraws() {
        val dao = LotoDatabase.get(this).drawDao()
        assets.open("loto7.csv").use { input ->
            BufferedReader(InputStreamReader(input, Charsets.UTF_8)).useLines { lines ->
                lines.drop(1).forEach { line ->
                    val p = line.split(',')
                    if (p.size < 9) return@forEach
                    val nums = p.subList(2, 9).mapNotNull { it.trim().toIntOrNull() }
                    if (nums.size != 7 || nums.distinct().size != 7 || nums.any { it !in 1..37 }) return@forEach
                    kotlinx.coroutines.runBlocking {
                        dao.insert(
                            DrawEntity(
                                date = p[1].trim(),
                                n1 = nums[0], n2 = nums[1], n3 = nums[2], n4 = nums[3],
                                n5 = nums[4], n6 = nums[5], n7 = nums[6]
                            )
                        )
                    }
                }
            }
        }
    }
}
