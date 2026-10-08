package com.femcare.ai

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.lifecycle.lifecycleScope
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.Constraints
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import com.femcare.ai.databinding.ActivityMainBinding
import androidx.health.connect.client.PermissionController
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

class MainActivity : ComponentActivity() {
    private lateinit var binding: ActivityMainBinding
    private lateinit var health: HealthConnectManager

    private val permissionLauncher =
        registerForActivityResult(
            PermissionController.createRequestPermissionResultContract()
        ) {
            syncIfReady()
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        health = HealthConnectManager(this)
        binding.loginButton.setOnClickListener { login() }
        binding.connectButton.setOnClickListener { connectHealth() }
        binding.syncButton.setOnClickListener { syncIfReady() }
        loadSavedState()
    }

    private fun login() {
        val username = binding.usernameInput.text?.toString()?.trim().orEmpty()
        val password = binding.passwordInput.text?.toString().orEmpty()
        if (username.isBlank() || password.isBlank()) {
            binding.statusText.text = "Enter your FemCare username and password."
            return
        }

        binding.statusText.text = "Logging in..."

        lifecycleScope.launch {
            try {
                val result = withContext(Dispatchers.IO) {
                    ApiClient.login(username, password)
                }

                getSharedPreferences("femcare", MODE_PRIVATE).edit()
                    .putString("api_token", result.token)
                    .putString("username", result.username)
                    .apply()

                binding.passwordInput.text?.clear()
                binding.statusText.text =
                    "Logged in as " + result.username + ". Connecting Health Connect..."
                scheduleBackgroundSync()
                connectHealth()
            } catch (e: Exception) {
                binding.statusText.text = e.message ?: "Login failed."
            }
        }
    }

    private fun connectHealth() {
        if (!health.isAvailable()) {
            binding.statusText.text = "Health Connect is not available on this device."
            return
        }

        lifecycleScope.launch {
            try {
                if (health.hasPermissions()) {
                    binding.statusText.text = "Health Connect is already connected."
                    scheduleBackgroundSync()
                    syncIfReady()
                    return@launch
                }

                permissionLauncher.launch(health.requiredPermissions)
            } catch (e: Exception) {
                binding.statusText.text =
                    e.message ?: "Could not open Health Connect permissions."
            }
        }
    }

    private fun syncIfReady() {
        lifecycleScope.launch {
            try {
                val prefs = getSharedPreferences("femcare", MODE_PRIVATE)
                val token = prefs.getString("api_token", null)

                if (token.isNullOrBlank()) {
                    binding.statusText.text = "Login first."
                    return@launch
                }

                if (!health.isAvailable()) {
                    binding.statusText.text = "Health Connect is unavailable."
                    return@launch
                }

                if (!health.hasPermissions()) {
                    binding.statusText.text = "Connect Health Connect first."
                    return@launch
                }

                binding.statusText.text = "Reading today's steps..."
                val steps = health.todaySteps()

                withContext(Dispatchers.IO) {
                    ApiClient.syncSteps(token, steps)
                }

                prefs.edit()
                    .putLong("last_steps", steps)
                    .putString("last_sync", java.time.Instant.now().toString())
                    .apply()

                binding.stepsText.text = steps.toString() + " steps"
                binding.syncText.text = "Synced to FemCare AI just now."
                binding.statusText.text = "Health data synced successfully."
            } catch (e: Exception) {
                binding.statusText.text = e.message ?: "Sync failed."
            }
        }
    }

    private fun scheduleBackgroundSync() {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val request = PeriodicWorkRequestBuilder<SyncWorker>(
            15,
            TimeUnit.MINUTES
        )
            .setConstraints(constraints)
            .build()

        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "femcare_health_sync",
            ExistingPeriodicWorkPolicy.UPDATE,
            request
        )
    }

    private fun loadSavedState() {
        val prefs = getSharedPreferences("femcare", MODE_PRIVATE)
        val username = prefs.getString("username", null)
        val steps = prefs.getLong("last_steps", 0)
        val lastSync = prefs.getString("last_sync", null)

        if (!username.isNullOrBlank()) {
            binding.statusText.text = "Logged in as " + username + ". Automatic sync is enabled."
            scheduleBackgroundSync()
            syncIfReady()
        }

        binding.stepsText.text = steps.toString()
        binding.syncText.text =
            if (lastSync.isNullOrBlank()) "Not synced yet"
            else "Last sync: " + lastSync
    }
}
