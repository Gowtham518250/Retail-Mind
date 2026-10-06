package com.retailmind.customer

import android.annotation.SuppressLint
import android.app.Activity
import android.content.Intent
import android.graphics.Bitmap
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.Bundle
import android.view.View
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout

class MainActivity : AppCompatActivity() {
    companion object {
        private const val HOME_URL = "https://retail-mind-web.onrender.com/"
    }

    private lateinit var webView: WebView
    private lateinit var swipe: SwipeRefreshLayout
    private lateinit var errorView: LinearLayout

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(0xFFFFFFFF.toInt())
        }

        swipe = SwipeRefreshLayout(this)
        webView = WebView(this)
        errorView = createErrorView()

        swipe.addView(webView, LinearLayout.LayoutParams(-1, -1))
        root.addView(swipe, LinearLayout.LayoutParams(-1, 0, 1f))
        root.addView(errorView, LinearLayout.LayoutParams(-1, 0))
        setContentView(root)

        configureWebView()
        swipe.setOnRefreshListener { loadCustomerApp() }
        loadCustomerApp()

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun configureWebView() {
        val settings = webView.settings
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.databaseEnabled = true
        settings.loadsImagesAutomatically = true
        settings.allowFileAccess = false
        settings.allowContentAccess = false
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        settings.mediaPlaybackRequiresUserGesture = false
        settings.setSupportZoom(false)
        settings.builtInZoomControls = false
        settings.displayZoomControls = false
        settings.userAgentString = settings.userAgentString + " RetailMindAndroid/1.0"

        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(webView, true)

        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val uri = request.url
                return if (uri.scheme == "http" || uri.scheme == "https") {
                    false
                } else {
                    try {
                        startActivity(Intent(Intent.ACTION_VIEW, uri))
                    } catch (_: Exception) {}
                    true
                }
            }

            override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
                errorView.visibility = View.GONE
                swipe.visibility = View.VISIBLE
            }

            override fun onPageFinished(view: WebView, url: String?) {
                swipe.isRefreshing = false
                errorView.visibility = View.GONE
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) showOfflineState()
            }
        }
    }

    private fun loadCustomerApp() {
        if (hasInternet()) {
            errorView.visibility = View.GONE
            swipe.visibility = View.VISIBLE
            webView.loadUrl(HOME_URL)
        } else {
            showOfflineState()
        }
    }

    private fun showOfflineState() {
        swipe.isRefreshing = false
        swipe.visibility = View.GONE
        errorView.visibility = View.VISIBLE
    }

    private fun hasInternet(): Boolean {
        val manager = getSystemService(ConnectivityManager::class.java)
        val network = manager.activeNetwork ?: return false
        val caps = manager.getNetworkCapabilities(network) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
               caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    private fun createErrorView(): LinearLayout {
        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = android.view.Gravity.CENTER
            setPadding(48, 48, 48, 48)
        }
        val title = TextView(this).apply {
            text = "You're offline"
            textSize = 22f
            gravity = android.view.Gravity.CENTER
        }
        val message = TextView(this).apply {
            text = "Check your internet connection and try again."
            textSize = 15f
            gravity = android.view.Gravity.CENTER
            setPadding(0, 16, 0, 24)
        }
        val retry = Button(this).apply {
            text = "Retry"
            setOnClickListener { loadCustomerApp() }
        }
        layout.addView(title)
        layout.addView(message)
        layout.addView(retry)
        return layout
    }

    override fun onDestroy() {
        webView.stopLoading()
        webView.destroy()
        super.onDestroy()
    }
}
