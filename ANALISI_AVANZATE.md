# Analisi Avanzate - LNP Stats

Questo documento elenca le analisi statistiche avanzate che possono essere implementate per i dati della Lega Nazionale Pallacanestro.

---

## Dati Disponibili

Per ogni partita di ogni giocatore abbiamo:
- **Statistiche base**: PT, AS, RT (RD+RO), PR, PP, ST, FF, FS, Minutes
- **Tiri**: 2PT, 3PT, TL (formato "made/attempted")
- **Contesto**: Team, Opponent, Gap (differenza punti finale), +/-
- **Metriche derivate**: VAL, pm_permin, pm_permin_adj

---

## 1. Clustering dei Giocatori

**Obiettivo**: Identificare automaticamente i "tipi" di giocatori basandosi sul loro profilo statistico.

**Metodologia**:
- Normalizzare le statistiche (z-score o min-max)
- Applicare K-means o clustering gerarchico
- Visualizzare con PCA o t-SNE

**Output atteso**:
- Cluster come: "Scorer", "Playmaker", "Rebounder", "Difensore", "All-around"
- Visualizzazione scatter 2D con cluster colorati

**Librerie**: `sklearn.cluster.KMeans`, `sklearn.decomposition.PCA`, `scipy.cluster.hierarchy`

---

## 2. Radar Chart per Confronto Giocatori

**Obiettivo**: Visualizzare il profilo multi-dimensionale di un giocatore e confrontarlo con altri.

**Metodologia**:
- Selezionare 6-8 statistiche chiave
- Normalizzare rispetto alla media del campionato (o percentili)
- Creare radar chart con Plotly

**Output atteso**:
- Grafico radar interattivo
- Possibilità di sovrapporre più giocatori
- Confronto con "giocatore medio"

**Librerie**: `plotly.graph_objects` (Scatterpolar)

---

## 3. Metriche di Consistenza

**Obiettivo**: Misurare quanto un giocatore è "affidabile" vs "streaky".

**Metriche**:
- **Deviazione Standard**: variabilità assoluta
- **Coefficiente di Variazione (CV)**: std/mean × 100 (variabilità relativa)
- **Range Interquartile (IQR)**: robusta agli outlier

**Output atteso**:
- Ranking giocatori per consistenza
- Flag "high variance" per giocatori imprevedibili
- Visualizzazione box plot per confronto

**Librerie**: `numpy`, `scipy.stats`

---

## 4. Correlazioni e Feature Importance

**Obiettivo**: Capire quali statistiche sono più correlate con la vittoria/performance.

**Metodologia**:
- Matrice di correlazione (Pearson/Spearman)
- Regressione lineare/Ridge per predire +/-
- Feature importance con Random Forest

**Output atteso**:
- Heatmap correlazioni
- Ranking delle statistiche più "impattanti"
- Modello predittivo semplice

**Librerie**: `scipy.stats.pearsonr`, `sklearn.linear_model`, `sklearn.ensemble`

---

## 5. Metriche Avanzate di Efficienza

**Obiettivo**: Calcolare metriche moderne usate in NBA/analytics.

### 5.1 Effective Field Goal % (eFG%)
```
eFG% = (FGM + 0.5 × 3PM) / FGA
```
Pesa i tiri da 3 per il loro valore extra.

### 5.2 True Shooting % (TS%)
```
TS% = PTS / (2 × (FGA + 0.44 × FTA))
```
Già implementato.

### 5.3 Usage Rate (USG%)
```
USG% = (FGA + 0.44 × FTA + TOV) / (Minutes × Team_Possessions)
```
Percentuale di possessi "usati" dal giocatore.

### 5.4 Assist Ratio
```
AST% = AST / (FGA + 0.44 × FTA + AST + TOV)
```

### 5.5 Turnover Ratio
```
TOV% = TOV / (FGA + 0.44 × FTA + TOV)
```

### 5.6 Player Efficiency Rating (PER) - Semplificato
```
PER = (PTS + REB + AST + STL + BLK - TO - Missed_FG - Missed_FT) / Minutes
```

**Librerie**: `pandas`, calcoli custom

---

## 6. Analisi Trend Temporale

**Obiettivo**: Identificare giocatori in miglioramento o calo durante la stagione.

**Metodologia**:
- Rolling average (ultime 5-10 partite)
- Regressione lineare su timeline
- Split prima/seconda metà stagione

**Output atteso**:
- Grafico trend per giocatore
- Flag "improving" / "declining"
- Confronto form recente vs media stagionale

**Librerie**: `pandas.rolling`, `scipy.stats.linregress`

---

## 7. Analisi Distribuzione

**Obiettivo**: Capire la forma della distribuzione delle statistiche.

**Metodologia**:
- Istogrammi e KDE (Kernel Density Estimation)
- Test di normalità (Shapiro-Wilk)
- Identificazione outlier (z-score > 2.5 o IQR method)

**Output atteso**:
- Distribuzione visuale per ogni statistica
- Lista outlier (performance eccezionali)
- Confronto distribuzioni tra campionati

**Librerie**: `scipy.stats.shapiro`, `scipy.stats.zscore`, `seaborn.kdeplot`

---

## 8. Similarità tra Giocatori

**Obiettivo**: Trovare giocatori con profili simili.

**Metodologia**:
- Distanza euclidea/coseno tra vettori statistici normalizzati
- Nearest neighbors

**Output atteso**:
- Per ogni giocatore: "Giocatori simili"
- Score di similarità
- Utile per scouting/sostituti

**Librerie**: `sklearn.neighbors.NearestNeighbors`, `scipy.spatial.distance`

---

## 9. Analisi di Squadra

**Obiettivo**: Metriche aggregate a livello squadra.

**Metriche**:
- **Offensive Rating**: punti per 100 possessi
- **Defensive Rating**: punti concessi per 100 possessi
- **Net Rating**: ORtg - DRtg
- **Pace**: possessi per partita

**Output atteso**:
- Ranking squadre per efficienza
- Scatter plot ORtg vs DRtg
- Identificazione stili di gioco

---

## 10. Test Statistici

**Obiettivo**: Determinare se le differenze sono statisticamente significative.

**Applicazioni**:
- Confronto performance casa/trasferta
- Confronto pre/post infortunio
- Differenze tra campionati

**Metodologia**:
- t-test per confronto medie
- Mann-Whitney U per distribuzioni non normali
- Intervalli di confidenza

**Librerie**: `scipy.stats.ttest_ind`, `scipy.stats.mannwhitneyu`

---

## Priorità Implementazione

| Priorità | Analisi | Complessità | Valore |
|----------|---------|-------------|--------|
| 1 | Radar Chart | Media | Alto |
| 2 | Clustering | Media | Alto |
| 3 | Consistenza | Bassa | Alto |
| 4 | Correlazioni | Bassa | Medio |
| 5 | Metriche Avanzate | Media | Alto |
| 6 | Trend Temporale | Media | Medio |
| 7 | Similarità | Media | Alto |
| 8 | Distribuzione | Bassa | Basso |
| 9 | Team Analysis | Alta | Medio |
| 10 | Test Statistici | Bassa | Basso |

---

## Note Tecniche

- Tutte le analisi devono gestire i valori mancanti (NaN)
- Filtrare giocatori con minuti minimi (es. > 100 min totali)
- Normalizzare per minuti quando appropriato
- Considerare il contesto (forza avversario, casa/trasferta)
