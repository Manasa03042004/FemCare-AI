# FemCare AI Android Health Bridge

This companion app connects FemCare AI to Android Health Connect.

It logs into the existing Flask app, requests Health Connect step + background-read permission, reads today's aggregated steps, sends them to the Flask API, and automatically syncs in the background with WorkManager. The website reads the synced value from the Flask database; the user does not need to keep the website open for syncing.

Open the android folder in Android Studio.

For the Android emulator, the backend URL is http://10.0.2.2:5000.
For a physical phone, replace the URL in ApiClient.kt with your computer's LAN IP, such as http://192.168.1.10:5000.

On Android 14+, Health Connect is part of the Android framework. On Android 13 and lower, install the Health Connect app.
