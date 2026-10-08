package com.femcare.ai
import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters

class SyncWorker(appContext: Context, workerParams: WorkerParameters) : CoroutineWorker(appContext, workerParams) {
    override suspend fun doWork(): Result {
        val prefs = applicationContext.getSharedPreferences("femcare", Context.MODE_PRIVATE)
        val token = prefs.getString("api_token", null) ?: return Result.failure()
        return try {
            val health = HealthConnectManager(applicationContext)
            if (!health.isAvailable() || !health.hasPermissions()) return Result.retry()
            if (!health.hasBackgroundReadPermission()) return Result.retry()
            val steps = health.todaySteps()
            ApiClient.syncSteps(token, steps)
            prefs.edit().putLong("last_steps", steps).putString("last_sync", java.time.Instant.now().toString()).apply()
            Result.success()
        } catch (_: Exception) {
            Result.retry()
        }
    }
}
