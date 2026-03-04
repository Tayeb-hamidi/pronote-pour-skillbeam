"use client";

import React from "react";

/* ── Constants ─────────────────────────────────────────── */

/**
 * Mistral Medium estimation:
 *   - Mistral Large 2 LCA: ~1.14 g CO₂eq / 400 tokens
 *   - Medium is ~3× smaller → ~0.4 g CO₂eq / 400 tokens
 *   - Average quiz item ≈ 600 tokens (prompt + response)
 *   - Per-item CO₂ = (600 / 400) × 0.4 = 0.6 g CO₂eq
 */
const CO2_PER_ITEM_GRAMS = 0.6;

/** Equivalences in g CO₂eq per unit of activity */
const EQUIV = {
  streamingPerSecond: 0.017,   // 1 s streaming vidéo (FR)
  covoituragePerMinute: 0.122, // 1 min covoiturage thermique
  metroPerMinute: 0.0045,      // 1 min métro
};

function formatDuration(totalUnits: number, unitLabel: string): string {
  if (totalUnits < 1) return `< 1 ${unitLabel}`;
  if (totalUnits < 60) return `${Math.round(totalUnits)} ${unitLabel}`;
  const minutes = Math.floor(totalUnits / 60);
  const remainder = Math.round(totalUnits % 60);
  if (unitLabel === "s") {
    return remainder > 0 ? `${minutes} min ${remainder} s` : `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const remainingMin = minutes % 60;
  return remainingMin > 0 ? `${hours} h ${remainingMin} min` : `${hours} h`;
}

/* ── Component ─────────────────────────────────────────── */

interface EcoImpactPanelProps {
  itemCount: number;
}

export function EcoImpactPanel({ itemCount }: EcoImpactPanelProps) {
  const co2Grams = itemCount * CO2_PER_ITEM_GRAMS;

  const streamingSec = co2Grams / EQUIV.streamingPerSecond;
  const covoitMin = co2Grams / EQUIV.covoituragePerMinute;
  const metroMin = co2Grams / EQUIV.metroPerMinute;

  return (
    <div className="eco-impact-panel">
      {/* Header */}
      <div className="eco-impact-header">
        <span className="eco-impact-cloud" aria-hidden>☁️</span>
        <span className="eco-impact-title">Impact écologique</span>
        <span className="eco-impact-badge">
          {co2Grams < 0.01 ? "< 0.01" : co2Grams.toFixed(2)} g
        </span>
      </div>

      {/* Model info */}
      <p className="eco-impact-model">
        🇫🇷 Modèle <strong>SkillBeam</strong> · hébergé en France
      </p>

      {/* CO₂ value */}
      <p className="eco-impact-value">
        Cette génération a un <strong>impact très faible</strong> : <strong>{co2Grams < 0.01 ? "< 0.01" : co2Grams.toFixed(2)} g eqCO₂</strong>
        <span className="eco-impact-info" title="Estimation basée sur le Lifecycle Assessment de Mistral AI. Inclut l'énergie d'inférence du modèle sur des serveurs en France (mix électrique bas carbone grâce au nucléaire)."> ⓘ</span>
      </p>

      {/* Equivalences */}
      <div className="eco-impact-equiv-grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
        <div className="eco-impact-equiv-card">
          <span className="eco-impact-equiv-icon" aria-hidden>📺</span>
          <span className="eco-impact-equiv-value">{formatDuration(streamingSec, "s")}</span>
          <span className="eco-impact-equiv-label">Streaming vidéo</span>
        </div>
        <div className="eco-impact-equiv-card">
          <span className="eco-impact-equiv-icon" aria-hidden>🚗</span>
          <span className="eco-impact-equiv-value">{formatDuration(covoitMin, "min")}</span>
          <span className="eco-impact-equiv-label">Voiture thermique</span>
        </div>
        <div className="eco-impact-equiv-card">
          <span className="eco-impact-equiv-icon" aria-hidden>🚇</span>
          <span className="eco-impact-equiv-value">{formatDuration(metroMin, "min")}</span>
          <span className="eco-impact-equiv-label">Transports en commun</span>
        </div>
        <div className="eco-impact-equiv-card">
          <span className="eco-impact-equiv-icon" aria-hidden>🌐</span>
          <span className="eco-impact-equiv-value">{Math.max(1, Math.round(co2Grams / 0.5))}</span>
          <span className="eco-impact-equiv-label">Pages web consultées</span>
        </div>
      </div>

      {/* Footer */}
      <p className="eco-impact-footer">
        Évaluez l&apos;empreinte carbone de vos usages numériques — données basées sur le <em>Lifecycle Assessment</em> Mistral AI × ADEME × Carbone 4.
      </p>
    </div>
  );
}
