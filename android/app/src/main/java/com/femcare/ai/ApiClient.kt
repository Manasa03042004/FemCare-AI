package com.femcare.ai
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object ApiClient {
    var baseUrl = "http://10.0.2.2:5000"
    data class LoginResult(val token: String, val username: String)

    fun login(username: String, password: String): LoginResult {
        val response = postJson("/api/login", JSONObject().put("username", username).put("password", password))
        if (!response.optBoolean("success")) throw IllegalStateException(response.optString("error", "Login failed"))
        return LoginResult(response.getString("token"), response.getString("username"))
    }

    fun syncSteps(token: String, steps: Long): JSONObject {
        return postJson("/api/health-sync", JSONObject()
            .put("date", java.time.LocalDate.now().toString())
            .put("steps", steps)
            .put("distance_meters", 0)
            .put("active_calories", 0)
            .put("exercise_minutes", 0)
            .put("sleep_minutes", 0), token)
    }

    private fun postJson(path: String, body: JSONObject, token: String? = null): JSONObject {
        val connection = (URL(baseUrl.trimEnd('/') + path).openConnection() as HttpURLConnection)
        connection.requestMethod = "POST"
        connection.connectTimeout = 10000
        connection.readTimeout = 15000
        connection.doOutput = true
        connection.setRequestProperty("Content-Type", "application/json")
        if (!token.isNullOrBlank()) connection.setRequestProperty("Authorization", "Bearer " + token)
        connection.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
        val stream = if (connection.responseCode in 200..299) connection.inputStream else connection.errorStream
        val text = stream.bufferedReader().use { it.readText() }
        val json = if (text.isBlank()) JSONObject() else JSONObject(text)
        if (connection.responseCode !in 200..299) throw IllegalStateException(json.optString("error", "Server error " + connection.responseCode))
        return json
    }
}
