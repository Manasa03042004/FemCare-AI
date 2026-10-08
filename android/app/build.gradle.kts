plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
android {
    namespace = "com.femcare.ai"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.femcare.ai"
        minSdk = 28
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"
    }
    buildFeatures { viewBinding = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}
dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.health.connect:connect-client:1.0.0-alpha11")
    implementation("androidx.work:work-runtime-ktx:2.10.0")
    implementation("androidx.activity:activity-ktx:1.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
}
