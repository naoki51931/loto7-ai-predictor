package com.naoki51931.loto7aipredictor

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.util.concurrent.TimeUnit

object Loto7OnlineSync {
    private const val SOURCE = "https://raw.githubusercontent.com/tk030-lotto/lotto-data-hub/main/data/loto7.json"
    private val tokyo = ZoneId.of("Asia/Tokyo")
    fun schedule(context: Context) {
        val request = PeriodicWorkRequestBuilder<Loto7SyncWorker>(6, TimeUnit.HOURS).build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork("loto7-results-sync", ExistingPeriodicWorkPolicy.KEEP, request)
    }
    fun shouldCheck(): Boolean {
        val now = java.time.ZonedDateTime.now(tokyo)
        // Friday after results are usually published, or later days to catch missed updates.
        return when (now.dayOfWeek) {
            DayOfWeek.FRIDAY -> !now.toLocalTime().isBefore(LocalTime.of(20, 0))
            DayOfWeek.SATURDAY, DayOfWeek.SUNDAY, DayOfWeek.MONDAY -> true
            else -> false
        }
    }
    suspend fun sync(context: Context): Int = withContext(Dispatchers.IO) {
        val connection = URL(SOURCE).openConnection() as HttpURLConnection
        connection.connectTimeout = 15000
        connection.readTimeout = 20000
        try {
            if (connection.responseCode != 200) error("HTTP ${connection.responseCode}")
            val data = JSONArray(connection.inputStream.bufferedReader().use { it.readText() })
            val dao = LotoDatabase.get(context).drawDao()
            val existing = dao.all().map { it.date }.toHashSet()
            var added = 0
            for (i in 0 until data.length()) {
                val row = data.getJSONObject(i)
                val date = row.optString("date")
                val nums = row.optJSONArray("numbers") ?: continue
                if (nums.length() != 7 || date in existing) continue
                val values = (0 until 7).map { nums.optInt(it, -1) }
                val parsedDate = runCatching { LocalDate.parse(date) }.getOrNull() ?: continue
                if (parsedDate.isAfter(LocalDate.now(tokyo)) || parsedDate.dayOfWeek != DayOfWeek.FRIDAY) continue
                if (values.distinct().size != 7 || values.any { it !in 1..37 }) continue
                dao.insert(DrawEntity(date = date, n1 = values[0], n2 = values[1], n3 = values[2], n4 = values[3], n5 = values[4], n6 = values[5], n7 = values[6]))
                existing.add(date)
                added++
            }
            added
        } finally { connection.disconnect() }
    }
}

class Loto7SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        if (!Loto7OnlineSync.shouldCheck()) return Result.success()
        return try { Loto7OnlineSync.sync(applicationContext); Result.success() }
        catch (_: Exception) { Result.retry() }
    }
}
