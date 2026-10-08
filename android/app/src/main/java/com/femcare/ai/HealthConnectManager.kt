package com.femcare.ai

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Instant
import java.time.ZoneId
import java.time.ZonedDateTime

class HealthConnectManager(context: Context) {
    private val appContext = context.applicationContext
    private val client = HealthConnectClient.getOrCreate(appContext)

    companion object {
        const val BACKGROUND_READ_PERMISSION =
            "android.permission.health.READ_HEALTH_DATA_IN_BACKGROUND"
    }

    val requiredPermissions = setOf(
        HealthPermission.getReadPermission(StepsRecord::class)
    )

    fun isAvailable(): Boolean {
        val status = HealthConnectClient.getSdkStatus(
            appContext,
            "com.google.android.apps.healthdata"
        )
        return status == HealthConnectClient.SDK_AVAILABLE
    }

    suspend fun hasPermissions(): Boolean {
        return client.permissionController
            .getGrantedPermissions()
            .containsAll(requiredPermissions)
    }

    suspend fun hasBackgroundReadPermission(): Boolean {
        return client.permissionController
            .getGrantedPermissions()
            .contains(BACKGROUND_READ_PERMISSION)
    }

    suspend fun todaySteps(): Long {
        val zone = ZoneId.systemDefault()
        val start = ZonedDateTime.now(zone)
            .toLocalDate()
            .atStartOfDay(zone)
            .toInstant()

        val result = client.aggregate(
            AggregateRequest(
                metrics = setOf(StepsRecord.COUNT_TOTAL),
                timeRangeFilter = TimeRangeFilter.between(start, Instant.now())
            )
        )

        return result[StepsRecord.COUNT_TOTAL] ?: 0L
    }
}
