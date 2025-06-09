package com.example.egaiswaybillapp

import android.content.Context
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import ru.evotor.egais.api.model.document.waybill.WayBill
import ru.evotor.egais.api.query.WayBillQuery

class MainActivity : AppCompatActivity() {

    private val prefs by lazy { getSharedPreferences("config", Context.MODE_PRIVATE) }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        promptAppUuidIfNeeded()
        setContentView(R.layout.activity_main)

        val etTtn = findViewById<EditText>(R.id.etTtn)
        val tvResult = findViewById<TextView>(R.id.tvResult)
        val btnQuery = findViewById<Button>(R.id.btnQuery)

        btnQuery.setOnClickListener {
            val ttn = etTtn.text.toString().trim()
            if (ttn.isNotEmpty()) {
                if (!isEgaisProviderAvailable()) {
                    tvResult.text = getString(R.string.provider_not_found)
                    return@setOnClickListener
                }

                val executor = WayBillQuery().number.equal(ttn)
                val result = StringBuilder()
                try {
                    executor.execute(this)?.use { cursor ->
                        while (cursor.moveToNext()) {
                            val wb: WayBill = cursor.getValue()
                            result.append(wb.toString()).append("\n")
                        }
                    }
                } catch (e: Exception) {
                    result.append(getString(R.string.query_failed, e.message))
                }
                if (result.isEmpty()) result.append(getString(R.string.not_found))
                tvResult.text = result.toString()
            }
        }
    }

    private fun promptAppUuidIfNeeded() {
        if (prefs.getString("app_uuid", null) == null) {
            val input = EditText(this)
            AlertDialog.Builder(this)
                .setTitle(R.string.enter_uuid)
                .setView(input)
                .setCancelable(false)
                .setPositiveButton(android.R.string.ok) { _, _ ->
                    prefs.edit().putString("app_uuid", input.text.toString()).apply()
                }
                .show()
        }
    }

    private fun isEgaisProviderAvailable(): Boolean {
        return packageManager.resolveContentProvider(
            "ru.evotor.egais.api.waybill",
            0
        ) != null
    }
}
