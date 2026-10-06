package com.femcare.ai
import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.aggregate.AggregateRequest
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime

class HealthConnectManager(context: Context) {
    private val appContext = context.applicationContext
    private val client = HealthConnectClient.getOrCreate(appContext)

    val requiredPermissions = setOf(HealthPermission.getReadPermission(StepsRecord::class))

    fun isAvailable(): Boolean {
        val status = HealthConnectClient.getSdkStatus(appContext, HealthConnectClient.DEFAULT_PROVIDER_PACKAGE_NAME)
        return status == HealthConnectClient.SDK_AVAILABLE
    }

    suspend fun hasPermissions(): Boolean {
        return client.permissionController.getGrantedPermissions().containsAll(requiredPermissions)
    }

    suspend fun todaySteps(): Long {
        val zone = ZoneId.systemDefault()
        val start = ZonedDateTime.now(zone).toLocalDate().atStartOfDay(zone).toInstant()
        val result = client.aggregate(AggregateRequest(
            metrics = setOf(StepsRecord.COUNT_TOTAL),
            timeRangeFilter = TimeRangeFilter.between(start, Instant.now())
        ))
        return result[StepsRecord.COUNT_TOTAL] ?: 0L
    }
}
