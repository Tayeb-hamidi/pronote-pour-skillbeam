import { type Dispatch, type SetStateAction } from "react";
import {
    ContentItem,
    ContentType,
    ExportFormat,
    ProjectAnalytics,
    PronoteImportResult,
    QualityPreview,
    SourceType,
} from "@/lib/types";
import {
    createProject,
    getContent,
    getProjectAnalytics,
    getSourceDocument,
    getQualityPreview,
    getExportDownload,
    importPronoteXml,
    launchExport,
    launchGenerate,
    launchIngest,
    login,
    pollJobUntilDone,
    saveContent,
    initSource,
    updateSourceDocument,
    uploadToPresigned,
} from "@/lib/api";
import { type BusyPhase, normalizeItemsForEditor, itemsNeedNormalization } from "@/lib/utils";
import { buildClozeExpectedAnswers, buildClozePatch } from "@/hooks/useItemEditor";

// ── Constants ──────────────────────────────────────────────

const MAX_UPLOAD_BYTES = 200 * 1024 * 1024;

const CLASS_LEVEL_OPTIONS = [
    "6e", "5e", "4e", "3e", "2nde", "1ere", "Terminale",
    "BTS", "L1", "L2", "L3", "M1", "M2",
    "Primaire", "CP", "CE1", "CE2", "CM1", "CM2",
];

// ── Types ──────────────────────────────────────────────────

export interface PronoteExerciseOption {
    value: string;
    title: string;
    subtitle: string;
    contentType: ContentType;
    generationHint: string;
}

export interface BusinessLogicState {
    // Auth
    token: string;
    setToken: Dispatch<SetStateAction<string>>;
    projectId: string;
    setProjectId: Dispatch<SetStateAction<string>>;
    // Progress & status
    setBusy: Dispatch<SetStateAction<boolean>>;
    setBusyPhase: Dispatch<SetStateAction<BusyPhase>>;
    setError: Dispatch<SetStateAction<string>>;
    setJobProgress: Dispatch<SetStateAction<number>>;
    setDownloadUrl: Dispatch<SetStateAction<string>>;
    setStep: Dispatch<SetStateAction<number>>;
    // Source
    sourceType: SourceType;
    selectedFile: File | null;
    freeText: string;
    topic: string;
    linkUrl: string;
    subject: string;
    setSubject: Dispatch<SetStateAction<string>>;
    classLevel: string;
    setClassLevel: Dispatch<SetStateAction<string>>;
    difficultyTarget: string;
    setDifficultyTarget: Dispatch<SetStateAction<string>>;
    learningGoal: string;
    setLearningGoal: Dispatch<SetStateAction<string>>;
    enableOcr: boolean;
    enableTableExtraction: boolean;
    smartCleaning: boolean;
    isPdfSelected: boolean;
    // Review
    setSourceReviewText: Dispatch<SetStateAction<string>>;
    sourceReviewText: string;
    setSourceQuality: Dispatch<SetStateAction<Record<string, unknown>>>;
    // Quality
    setQualityPreview: Dispatch<SetStateAction<QualityPreview | null>>;
    setAnalytics: Dispatch<SetStateAction<ProjectAnalytics | null>>;
    // Generation
    evaluationType: string;
    instructions: string;
    selectedPronoteOptions: PronoteExerciseOption[];
    selectedNonPronoteTypes: ContentType[];
    pronoteModeCounts: Record<string, number>;
    selectedPronoteModes: string[];
    matchingPairsPerQuestion: number;
    pronoteRequestedCount: number;
    nonPronoteRequestedCount: number;
    generationCount: number;
    // Content
    items: ContentItem[];
    setItems: Dispatch<SetStateAction<ContentItem[]>>;
    contentSetId: string;
    setContentSetId: Dispatch<SetStateAction<string>>;
    // Export
    exportFormat: ExportFormat;
    setExportFormat: Dispatch<SetStateAction<ExportFormat>>;
    pronoteShuffleAnswers: boolean;
    // Import
    pronoteImportXml: string;
    pronoteImportFilename: string;
    replaceContentOnImport: boolean;
    normalizeImportedItems: boolean;
    openEditorAfterImport: boolean;
    setImportResult: Dispatch<SetStateAction<PronoteImportResult | null>>;
    setShowPronoteImportPanel: Dispatch<SetStateAction<boolean>>;
}

// ── Hook ───────────────────────────────────────────────────

export function useBusinessLogic(state: BusinessLogicState) {
    // ── Auth ──

    async function ensureAuthAndProject(): Promise<{ authToken: string; project: string }> {
        let authToken = state.token;
        if (!authToken) {
            const email = process.env.NEXT_PUBLIC_AUTH_EMAIL ?? "demo@skillbeam.local";
            const password = process.env.NEXT_PUBLIC_AUTH_PASSWORD ?? "demo123";
            const auth = await login(email, password);
            authToken = auth.access_token;
            state.setToken(authToken);
            if (typeof window !== "undefined") {
                sessionStorage.setItem("sb_token", authToken);
            }
        }
        let project = state.projectId;
        if (!project) {
            const created = await createProject(authToken, "Projet Wizard");
            project = created.id;
            state.setProjectId(project);
        }
        return { authToken, project };
    }

    // ── Refresh helpers ──

    async function refreshQualityPreview(authToken: string, project: string): Promise<void> {
        try {
            const preview = await getQualityPreview(authToken, project);
            state.setQualityPreview(preview);
        } catch (e) {
            state.setQualityPreview(null);
            state.setError(e instanceof Error ? e.message : "Impossible de calculer la qualité pédagogique");
        }
    }

    async function refreshAnalytics(authToken: string, project: string): Promise<void> {
        try {
            const data = await getProjectAnalytics(authToken, project);
            state.setAnalytics(data);
        } catch (e) {
            state.setError(e instanceof Error ? e.message : "Impossible de charger les analytics");
        }
    }

    async function loadSourceDocumentForReview(authToken: string, project: string): Promise<void> {
        const document = await getSourceDocument(authToken, project);
        state.setSourceReviewText(document.plain_text);

        const metadata = document.metadata ?? {};
        const quality = metadata.source_quality;
        if (quality && typeof quality === "object" && !Array.isArray(quality)) {
            state.setSourceQuality(quality as Record<string, unknown>);
        } else {
            state.setSourceQuality({});
        }
        if (!state.subject && typeof metadata.subject === "string" && metadata.subject.trim()) {
            state.setSubject(metadata.subject.trim());
        }
        if (
            typeof metadata.class_level === "string" &&
            metadata.class_level.trim() &&
            CLASS_LEVEL_OPTIONS.includes(metadata.class_level.trim())
        ) {
            state.setClassLevel(metadata.class_level.trim());
        }
        if (typeof metadata.difficulty_target === "string" && metadata.difficulty_target.trim()) {
            state.setDifficultyTarget(metadata.difficulty_target.trim().toLowerCase());
        }
        if (!state.learningGoal && typeof metadata.learning_goal === "string" && metadata.learning_goal.trim()) {
            state.setLearningGoal(metadata.learning_goal.trim());
        }
    }

    // ── Ingest ──

    async function handleIngest(): Promise<void> {
        state.setBusy(true);
        state.setBusyPhase("ingest");
        state.setError("");
        state.setDownloadUrl("");
        state.setJobProgress(0);

        try {
            const { authToken, project } = await ensureAuthAndProject();
            let sourceAssetId: string | undefined;

            if (state.sourceType === "document") {
                if (!state.selectedFile) throw new Error("Document requis");
                if (state.selectedFile.size > MAX_UPLOAD_BYTES) throw new Error("Le fichier depasse 200MB");

                const init = await initSource(authToken, project, {
                    source_type: state.sourceType,
                    filename: state.selectedFile.name,
                    mime_type: state.selectedFile.type,
                    size_bytes: state.selectedFile.size,
                    enable_ocr: state.isPdfSelected ? state.enableOcr : false,
                    enable_table_extraction: state.isPdfSelected ? state.enableTableExtraction : false,
                    smart_cleaning: state.isPdfSelected ? state.smartCleaning : false,
                });
                sourceAssetId = init.asset_id;
                if (!init.upload_url) throw new Error("URL upload manquante");
                await uploadToPresigned(init.upload_url, state.selectedFile);
            } else {
                const init = await initSource(authToken, project, {
                    source_type: state.sourceType,
                    raw_text: state.sourceType === "text" ? state.freeText : undefined,
                    topic: state.sourceType === "theme" ? state.topic : undefined,
                    link_url: state.sourceType === "youtube" ? state.linkUrl : undefined,
                    subject: state.subject.trim() || undefined,
                    class_level: state.classLevel.trim() || undefined,
                    difficulty_target: state.difficultyTarget.trim() || undefined,
                    learning_goal: state.learningGoal.trim() || undefined,
                });
                sourceAssetId = init.asset_id;
            }

            const ingest = await launchIngest(authToken, project, sourceAssetId);
            const job = await pollJobUntilDone(authToken, ingest.job_id, (next) => state.setJobProgress(next.progress));
            state.setJobProgress(job.progress);
            await loadSourceDocumentForReview(authToken, project);
            state.setStep(3);
        } catch (e) {
            state.setError(e instanceof Error ? e.message : "Erreur ingestion");
        } finally {
            state.setBusy(false);
            state.setBusyPhase(null);
        }
    }

    // ── Generation ──

    function buildGenerationPlan(options?: { pronoteOnly?: boolean }): {
        contentTypes: ContentType[];
        maxItems: number;
        instructions?: string;
    } {
        const pronoteOnly = options?.pronoteOnly ?? false;
        const activePronoteOptions = state.selectedPronoteOptions;
        const pronoteTypes = activePronoteOptions.map((o) => o.contentType);
        const baseTypes = pronoteOnly ? [] : state.selectedNonPronoteTypes;
        const contentTypes = Array.from(new Set([...pronoteTypes, ...baseTypes]));

        const pronoteDistribution = activePronoteOptions
            .map((o) => `- ${o.title}: ${Math.min(100, Math.max(1, state.pronoteModeCounts[o.value] ?? 1))}`)
            .join("\n");
        const pronoteHints = activePronoteOptions.map((o) => `- ${o.title}: ${o.generationHint}`).join("\n");
        const pronoteModeJson = activePronoteOptions.reduce<Record<string, number>>((acc, o) => {
            acc[o.value] = Math.min(100, Math.max(1, state.pronoteModeCounts[o.value] ?? 1));
            return acc;
        }, {});
        if (state.selectedPronoteModes.includes("matching")) {
            pronoteModeJson["matching_pairs_per_question"] = state.matchingPairsPerQuestion;
        }

        const sections = [
            state.evaluationType
                ? `TYPE D'EVALUATION: ${state.evaluationType === "diagnostic" ? "Évaluation diagnostique — test de positionnement avant une nouvelle séquence pour évaluer le niveau initial des élèves. Privilégier des questions de connaissance générale et de prérequis." : state.evaluationType === "formative" ? "Évaluation formative — évaluation en cours de séquence pédagogique pour vérifier la compréhension et les compétences en cours d'acquisition. Privilégier des questions progressives et formatives." : "Évaluation sommative — évaluation de fin de séquence pour valider les compétences travaillées. Privilégier des questions de synthèse et d'application complètes."}`
                : "",
            state.instructions.trim(),
            state.learningGoal.trim() ? `Objectif: ${state.learningGoal.trim()}` : "",
            pronoteDistribution ? `Distribution pronote demandee (nb d'items):\n${pronoteDistribution}` : "",
            pronoteHints ? `Contraintes pronote par type:\n${pronoteHints}` : "",
            activePronoteOptions.length > 0 ? `PRONOTE_MODES_JSON: ${JSON.stringify(pronoteModeJson)}` : "",
            "Style attendu: ne numerotez jamais les enonces (pas de Q1, Question 1, Item 1). Gardez uniquement la question.",
        ].filter(Boolean);

        const nonPronoteCount = pronoteOnly ? 0 : state.nonPronoteRequestedCount;
        const desired = state.pronoteRequestedCount + nonPronoteCount;

        return {
            contentTypes,
            maxItems: Math.min(100, Math.max(1, desired || state.generationCount)),
            instructions: sections.length > 0 ? sections.join("\n\n") : undefined,
        };
    }

    async function runGenerate(plan: {
        contentTypes: ContentType[];
        maxItems: number;
        instructions?: string;
    }): Promise<void> {
        state.setBusy(true);
        state.setBusyPhase("generate");
        state.setError("");
        state.setJobProgress(0);
        try {
            const { authToken, project } = await ensureAuthAndProject();
            const reviewedText = state.sourceReviewText.trim();
            if (reviewedText.length > 0) {
                await updateSourceDocument(authToken, project, { plain_text: reviewedText });
            }
            const generated = await launchGenerate(authToken, project, {
                content_types: plan.contentTypes,
                instructions: plan.instructions,
                max_items: plan.maxItems,
                language: "fr",
                level: state.classLevel || "intermediate",
                subject: state.subject.trim() || undefined,
                class_level: state.classLevel.trim() || undefined,
                difficulty_target: state.difficultyTarget.trim() || undefined,
            });
            const job = await pollJobUntilDone(authToken, generated.job_id, (next) =>
                state.setJobProgress(next.progress)
            );
            state.setJobProgress(job.progress);

            const content = await getContent(authToken, project);
            state.setContentSetId(content.content_set_id);
            state.setItems(normalizeItemsForEditor(content.items));
            await refreshQualityPreview(authToken, project);
            await refreshAnalytics(authToken, project);
            state.setStep(4);
        } catch (e) {
            state.setError(e instanceof Error ? e.message : "Erreur generation");
        } finally {
            state.setBusy(false);
            state.setBusyPhase(null);
        }
    }

    async function handleGenerate(): Promise<void> {
        const plan = buildGenerationPlan();
        if (plan.contentTypes.length === 0) {
            state.setError("Selectionnez au moins un type de contenu a generer.");
            return;
        }
        await runGenerate(plan);
    }

    async function handleQuickPronoteGenerate(): Promise<void> {
        const plan = buildGenerationPlan({ pronoteOnly: true });
        if (plan.contentTypes.length === 0) {
            state.setError("Selectionnez au moins un type d'exercice Pronote.");
            return;
        }
        await runGenerate(plan);
    }

    // ── Save & Export ──

    function triggerBrowserDownload(url: string): void {
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", "");
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }

    async function handleSaveContent(): Promise<void> {
        state.setBusy(true);
        state.setBusyPhase("save");
        state.setError("");
        try {
            const { authToken, project } = await ensureAuthAndProject();
            const normalizedItems = normalizeItemsForEditor(state.items).map((item) => {
                if (item.item_type !== "cloze") return item;
                const clozePatch = buildClozePatch(item, buildClozeExpectedAnswers(item));
                return { ...item, correct_answer: clozePatch.correct_answer };
            });
            state.setItems(normalizedItems);
            const saved = await saveContent(authToken, project, {
                content_set_id: state.contentSetId,
                items: normalizedItems,
            });
            state.setItems(normalizeItemsForEditor(saved.items));
            await refreshQualityPreview(authToken, project);
            await refreshAnalytics(authToken, project);
            state.setStep(5);
        } catch (e) {
            state.setError(e instanceof Error ? e.message : "Erreur sauvegarde");
        } finally {
            state.setBusy(false);
            state.setBusyPhase(null);
        }
    }

    async function handleExport(): Promise<void> {
        state.setBusy(true);
        state.setBusyPhase("export");
        state.setError("");
        state.setDownloadUrl("");
        state.setJobProgress(0);
        try {
            const { authToken, project } = await ensureAuthAndProject();
            const launch = await launchExport(authToken, project, {
                format: state.exportFormat,
                options:
                    state.exportFormat === "pronote_xml"
                        ? {
                            answernumbering: "123",
                            niveau: state.classLevel.trim() || "",
                            matiere: state.subject.trim() || "",
                            shuffle_answers: state.pronoteShuffleAnswers,
                        }
                        : {},
            });
            const job = await pollJobUntilDone(authToken, launch.job_id, (next) =>
                state.setJobProgress(next.progress)
            );
            if (!job.result_id) throw new Error("Export termine sans identifiant d'artefact");
            const downloadable = await getExportDownload(authToken, job.result_id);
            state.setDownloadUrl(downloadable.url);
            triggerBrowserDownload(downloadable.url);
            await refreshAnalytics(authToken, project);
        } catch (e) {
            state.setError(e instanceof Error ? e.message : "Erreur export");
        } finally {
            state.setBusy(false);
            state.setBusyPhase(null);
        }
    }

    async function handleSaveAndDownloadPronote(): Promise<void> {
        state.setBusy(true);
        state.setBusyPhase("export");
        state.setError("");
        state.setDownloadUrl("");
        state.setJobProgress(0);
        state.setExportFormat("pronote_xml");

        try {
            const { authToken, project } = await ensureAuthAndProject();
            const normalizedItems = normalizeItemsForEditor(state.items).map((item) => {
                if (item.item_type !== "cloze") return item;
                const clozePatch = buildClozePatch(item, buildClozeExpectedAnswers(item));
                return { ...item, correct_answer: clozePatch.correct_answer };
            });
            state.setItems(normalizedItems);
            const saved = await saveContent(authToken, project, {
                content_set_id: state.contentSetId,
                items: normalizedItems,
            });
            state.setItems(normalizeItemsForEditor(saved.items));
            await refreshQualityPreview(authToken, project);

            const launch = await launchExport(authToken, project, {
                format: "pronote_xml",
                options: {
                    answernumbering: "123",
                    niveau: state.classLevel.trim() || "",
                    matiere: state.subject.trim() || "",
                    shuffle_answers: state.pronoteShuffleAnswers,
                },
            });
            const job = await pollJobUntilDone(authToken, launch.job_id, (next) =>
                state.setJobProgress(next.progress)
            );
            if (!job.result_id) throw new Error("Export termine sans identifiant d'artefact");
            const downloadable = await getExportDownload(authToken, job.result_id);
            state.setDownloadUrl(downloadable.url);
            triggerBrowserDownload(downloadable.url);
            await refreshAnalytics(authToken, project);
        } catch (e) {
            state.setError(e instanceof Error ? e.message : "Erreur export PRONOTE");
        } finally {
            state.setBusy(false);
            state.setBusyPhase(null);
        }
    }

    // ── Import ──

    async function handleImportPronoteXml(): Promise<void> {
        if (!state.pronoteImportXml.trim()) {
            state.setError("Collez le XML Pronote avant import.");
            return;
        }
        state.setBusy(true);
        state.setBusyPhase("save");
        state.setError("");
        try {
            const { authToken, project } = await ensureAuthAndProject();
            const imported = await importPronoteXml(authToken, project, {
                xml_content: state.pronoteImportXml.trim(),
                source_filename: state.pronoteImportFilename.trim() || undefined,
                replace_current_content: state.replaceContentOnImport,
            });
            state.setImportResult(imported);
            const content = await getContent(authToken, project);
            state.setContentSetId(content.content_set_id);
            state.setItems(
                state.normalizeImportedItems ? normalizeItemsForEditor(content.items) : content.items
            );
            await refreshQualityPreview(authToken, project);
            await refreshAnalytics(authToken, project);
            state.setShowPronoteImportPanel(false);
            state.setStep(state.openEditorAfterImport ? 4 : 3);
        } catch (e) {
            state.setError(e instanceof Error ? e.message : "Erreur import Pronote");
        } finally {
            state.setBusy(false);
            state.setBusyPhase(null);
        }
    }

    return {
        ensureAuthAndProject,
        refreshQualityPreview,
        refreshAnalytics,
        loadSourceDocumentForReview,
        handleIngest,
        buildGenerationPlan,
        runGenerate,
        handleGenerate,
        handleQuickPronoteGenerate,
        handleSaveContent,
        handleExport,
        handleSaveAndDownloadPronote,
        triggerBrowserDownload,
        handleImportPronoteXml,
    };
}
