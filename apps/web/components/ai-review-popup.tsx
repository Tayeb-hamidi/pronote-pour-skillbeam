"use client";

import Image from "next/image";

interface AiReviewPopupProps {
    open: boolean;
    onClose: () => void;
}

export function AiReviewPopup({ open, onClose }: AiReviewPopupProps) {
    if (!open) return null;

    return (
        <div
            className="ai-review-popup-backdrop"
            onClick={onClose}
            onKeyDown={(e: React.KeyboardEvent) => {
                if (e.key === "Escape") onClose();
            }}
            tabIndex={-1}
            role="dialog"
            aria-modal="true"
            aria-label="Relecture recommandée"
        >
            <div
                className="ai-review-popup ai-review-popup-redesigned"
                onClick={(e: React.MouseEvent) => e.stopPropagation()}
            >
                <button
                    type="button"
                    className="ai-review-popup-close-btn"
                    onClick={onClose}
                    aria-label="Fermer"
                >
                    ×
                </button>

                <div className="ai-review-popup-logo-wrap">
                    <Image
                        src="/skillbeam-logo.png"
                        alt="SkillBeam"
                        width={80}
                        height={80}
                        className="ai-review-popup-logo"
                    />
                </div>

                <p className="ai-review-popup-title-new">Relecture avant utilisation</p>

                <p className="ai-review-popup-subtitle">
                    Les questions ci-après ont été générées par <strong>intelligence artificielle</strong>.
                    Veuillez relire et vérifier les propositions de SkillBeam avant de les utiliser en classe.
                </p>

                <div className="ai-review-popup-actions">
                    <button
                        type="button"
                        className="ai-review-popup-accept"
                        onClick={onClose}
                    >
                        ✓ J&apos;ai compris, voir les questions
                    </button>
                </div>
            </div>
        </div>
    );
}
