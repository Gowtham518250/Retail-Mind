# Keep the WebView activity and JavaScript bridge surface.
-keep class com.retailmind.customer.MainActivity { *; }

# AndroidX WebKit uses reflection internally in some configurations.
-keep class androidx.webkit.** { *; }
