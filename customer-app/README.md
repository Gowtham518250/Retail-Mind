# Retail Mind Customer Android App

This is the Android application wrapper for the existing Retail Mind customer web application.

## Architecture

The Android app is a native Kotlin WebView shell. It loads the same production customer storefront used by the website:

https://retail-mind-web.onrender.com/

The website remains available independently. Both clients use the same backend, authentication, checkout, orders, and realtime functionality.

## Build

Open this `customer-app/android` directory in Android Studio and build the `app` module.

Release builds require the normal Android signing configuration for Play Store publishing.

## Package

`com.retailmind.customer`

## Production URL

The production URL is defined in `MainActivity.kt` as `PRODUCTION_URL`. Do not put credentials or API secrets in the Android project.
