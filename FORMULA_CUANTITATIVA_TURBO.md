# ⚡ KUQUANT TURBO (ALPHA-X) • FÓRMULA CUANTITATIVA AGRESIVA DE SCALPING Y RUPTURA
**Documento Técnico Propietario & Propiedad Intelectual • Versión 2.0**  
*Estrategia: Volatility Squeeze Breakout + Order Book Acceleration + Trailing Exit Dinámico*

---

## 🏎️ 1. Filosofía de la Nueva Fórmula (Diferencias con la Versión Clásica)

| Parámetro | Bot 1 (KuQuant Classic) | Bot 2 (KuQuant Turbo / Alpha-X) |
| :--- | :--- | :--- |
| **Enfoque** | Tendencial + Filtro Macro NLP | **Scalping de Momentum & Ruptura de Volatilidad (Breakout)** |
| **Riesgo por Trade ($R$)** | $1.0\%$ (Conservador) | **$2.0\%$ (Agresivo / Alto Rendimiento)** |
| **Frecuencia Operativa** | 2 - 4 operaciones / día | **6 - 15 operaciones / día** (Scalping rápido) |
| **Salidas de Posición** | TP fijo a $1.5 \times \text{ATR}$ | **Take Profit Dinámico Multietapa + Trailing Stop Loss** |
| **Circuit Breaker Diario** | $3.0\%$ Max Drawdown | **$5.0\%$ Max Drawdown** |

---

## 📐 2. Ecuación Maestra de Señal Turbo ($\alpha_{\text{turbo}}$)

La señal direccional $\alpha_{\text{turbo}} \in [-1.0, +1.0]$ evalúa el estallido de volatilidad y la aceleración de liquidez:

$$\alpha_{\text{turbo}} = 0.35 \cdot S_{\text{squeeze}} + 0.35 \cdot S_{\text{OBI\_accel}} + 0.20 \cdot S_{\text{momentum}} + 0.10 \cdot S_{\text{NLP}}$$

---

### A. Componente 1: Compresión y Ruptura de Volatilidad (*Bollinger-Keltner Squeeze*)

Detecta cuando la volatilidad se comprime y explota en una dirección:

$$S_{\text{squeeze}} = \%B - 0.50 \quad \text{donde} \quad \%B = \frac{P_{\text{actual}} - \text{LowerBand}_{\text{BB}}}{\text{UpperBand}_{\text{BB}} - \text{LowerBand}_{\text{BB}}}$$

* **Filtro de Expansión (Bandwidth Expansion)**:
  $$\text{BandWidth} = \frac{\text{UpperBand}_{\text{BB}} - \text{LowerBand}_{\text{BB}}}{\text{SMA}_{20}(P)}$$

---

### B. Componente 2: Aceleración del Desbalance del Libro ($\frac{d\text{OBI}}{dt}$)

No solo mide si hay más compras que ventas, sino la **velocidad de cambio** en el libro de órdenes en microsegundos:

$$S_{\text{OBI\_accel}} = \text{OBI}_{t} + 0.5 \cdot \left( \frac{\text{OBI}_{t} - \text{OBI}_{t-1}}{\Delta t} \right)$$

---

### C. Componente 3: Momentum de Scalping Rápido ($S_{\text{momentum}}$)

Basado en oscilador estocástico rápido ($K\%$) + MACD rápido ($3, 10, 16$):

$$S_{\text{momentum}} = \frac{\text{MACD}_{\text{fast}}}{\text{ATR}_7} \times \text{Norm}(\text{Stoch}_K)$$

---

## 🛡️ 3. Gestión de Riesgo y Trailing Stop Multietapa

1. **Dimensionamiento de Posición (Riesgo del 2.0%)**:
   $$U = \frac{\text{Capital Total} \times 0.02}{|P_{\text{entrada}} - P_{\text{StopLoss}}|}$$

2. **Trailing Stop Dinámico (*Chandelier Scalp Exit*)**:
   A medida que el precio se mueve a favor, el Stop Loss se reajusta automáticamente al máximo alcanzado menos $0.8 \times \text{ATR}$, asegurando ganancias flotantes sin dejar que se conviertan en pérdidas.

3. **Take Profit Escalonado**:
   * **$TP_1$ ($1.2 \times \text{ATR}$)**: Cierre del 50% de la posición para asegurar beneficio inmediato.
   * **$TP_2$ ($2.5 \times \text{ATR}$ o Trailing)**: El 50% restante corre para capturar movimientos explosivos.

---
*KuQuant Turbo Engine • Propiedad Intelectual • 2026*
