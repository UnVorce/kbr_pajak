# notebooks/

Tempat `colab_extract.ipynb` — notebook ekstraksi LLM sesuai spec Bagian 8.

Dibuat pada **Fase 5** (pilot LLM), dengan perilaku: cek GPU dulu (berhenti
jelas bila tidak memenuhi `config/model_config.yaml`), mount Drive, baca
`chunks/pending/` sambil lewati `result_key` yang sudah ada (resume), tulis
`llm_results/` append + flush rutin, tangani OOM/non-JSON, catat latency/token.

Untuk saat ini folder ini sengaja kosong — notebook bukan bagian Fase 0.
