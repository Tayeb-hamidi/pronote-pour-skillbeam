"use client";

import clsx from "clsx";
import Image from "next/image";
import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { AiReviewPopup } from "@/components/ai-review-popup";
import { ConversionOverlay } from "@/components/conversion-overlay";
import { PronoteLogoIcon, EleaLogoIcon } from "@/components/pronote-icons";
import { Stepper } from "@/components/stepper";
import { Tile } from "@/components/tile";
import { useItemEditor, buildClozeExpectedAnswers, buildClozePatch } from "@/hooks/useItemEditor";
import { useBusinessLogic } from "@/hooks/useBusinessLogic";
import {
  type BusyPhase,
  type PronoteExerciseMode,
  formatFileSize as formatFileSizeUtil,
  labelDifficulty as labelDifficultyUtil,
  normalizeDifficultyValue as normalizeDifficultyValueUtil,
  labelItemType as labelItemTypeUtil,
} from "@/lib/utils";
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
  uploadToPresigned
} from "@/lib/api";
import {
  ContentItem,
  ContentType,
  ExportFormat,
  ProjectAnalytics,
  PronoteImportResult,
  QualityPreview,
  SourceType
} from "@/lib/types";

const STEP_LABELS = ["Source", "Ingestion", "Generation", "Edition", "Export"];
const MAX_UPLOAD_BYTES = 200 * 1024 * 1024;

const CLASS_LEVEL_OPTIONS = [
  "6e",
  "5e",
  "4e",
  "3e",
  "2nde",
  "1ere",
  "Terminale",
  "BTS",
  "Licence"
];

const SOURCE_OPTIONS: Array<{
  value: SourceType;
  title: string;
  subtitle: string;
  badge: string;
}> = [
    { value: "document", title: "Document", subtitle: "PDF, DOCX, PPTX, TXT, MD", badge: "DOC" },
    { value: "text", title: "Texte", subtitle: "Saisie manuelle rapide", badge: "TXT" },
    { value: "theme", title: "Thématique", subtitle: "Sujet à développer", badge: "TOP" },
    { value: "youtube", title: "YouTube", subtitle: "URL video avec sous-titres", badge: "YT" }
  ];

const CONTENT_OPTIONS: Array<{ value: ContentType; title: string; subtitle: string }> = [
  {
    value: "mcq",
    title: "QCM Pronote",
    subtitle: "Bonne reponse + distracteurs"
  },
  { value: "course_structure", title: "Structure cours", subtitle: "TOC, glossaire, concepts, resumes" },
  { value: "poll", title: "Sondage", subtitle: "Choix multiples sans bonne reponse" },
  { value: "open_question", title: "Questions ouvertes", subtitle: "Attendus de correction" },
  { value: "cloze", title: "Textes a trous", subtitle: "Completions ciblees" },
  { value: "brainstorming", title: "Brainstorming", subtitle: "Categories + idees" },
  { value: "flashcards", title: "Flashcards", subtitle: "Recto/verso revision" }
];


const PRONOTE_EXERCISE_OPTIONS: Array<{
  value: PronoteExerciseMode;
  title: string;
  subtitle: string;
  contentType: ContentType;
  generationHint: string;
}> = [
    {
      value: "single_choice",
      title: "Choix unique",
      subtitle: "1 bonne reponse parmi plusieurs",
      contentType: "mcq",
      generationHint: "1 seule bonne reponse clairement identifiable."
    },
    {
      value: "multiple_choice",
      title: "Choix multiple",
      subtitle: "Plusieurs bonnes reponses",
      contentType: "poll",
      generationHint: "proposer plusieurs options pertinentes pour selection multiple."
    },
    {
      value: "numeric_value",
      title: "Valeur numerique",
      subtitle: "Reponse attendue en format numerique",
      contentType: "open_question",
      generationHint: "attendre une reponse numerique et une unite si utile."
    },
    {
      value: "free_response",
      title: "Reponse a saisir",
      subtitle: "Texte libre court",
      contentType: "open_question",
      generationHint: "reponse courte a saisir avec formulation precise."
    },
    {
      value: "spelling",
      title: "Epellation",
      subtitle: "Mot ou expression a epeler",
      contentType: "open_question",
      generationHint: "demander explicitement une reponse epellee lettre par lettre."
    },
    {
      value: "cloze_free",
      title: "Texte a trous libre",
      subtitle: "Sans liste d'aide",
      contentType: "cloze",
      generationHint: "texte a trous sans proposition de reponses."
    },
    {
      value: "cloze_list_unique",
      title: "Texte a trous liste unique",
      subtitle: "Liste commune pour tous les trous",
      contentType: "cloze",
      generationHint: "texte a trous avec banque commune de mots."
    },
    {
      value: "cloze_list_variable",
      title: "Texte a trous liste variable",
      subtitle: "Une liste par trou",
      contentType: "cloze",
      generationHint: "texte a trous avec options specifiques a chaque trou."
    },
    {
      value: "matching",
      title: "Association",
      subtitle: "Relier elements gauche / droite",
      contentType: "matching",
      generationHint: "generer des paires a associer, chaque element gauche correspond a un element droite unique."
    }
  ];

const PRONOTE_EXERCISE_FAMILIES: Array<{
  title: string;
  subtitle: string;
  modes: PronoteExerciseMode[];
}> = [
    {
      title: "QCM",
      subtitle: "Choix parmi des propositions",
      modes: ["single_choice", "multiple_choice"]
    },
    {
      title: "Saisie de reponse",
      subtitle: "Reponse numerique, texte libre, epellation",
      modes: ["numeric_value", "free_response", "spelling"]
    },
    {
      title: "Texte a trous",
      subtitle: "Libre, liste unique, liste variable",
      modes: ["cloze_free", "cloze_list_unique", "cloze_list_variable"]
    },
    {
      title: "Association",
      subtitle: "Relier des elements entre eux",
      modes: ["matching"]
    }
  ];

const EXPORT_OPTIONS: Array<{ value: ExportFormat; title: string; subtitle: string }> = [
  { value: "docx", title: "Word (DOCX)", subtitle: "Document modifiable" },
  { value: "pdf", title: "PDF", subtitle: "Mise en page rapide" },
  { value: "xlsx", title: "Excel (XLSX)", subtitle: "Table de questions" },
  { value: "moodle_xml", title: "Moodle XML", subtitle: "Import quiz Moodle" },
  { value: "pronote_xml", title: "PRONOTE XML", subtitle: "Format XML strict pronote" },
  { value: "qti", title: "QTI", subtitle: "Placeholder structure IMS" },
  { value: "h5p", title: "H5P", subtitle: "QuestionSet best-effort" },
  { value: "anki", title: "Anki", subtitle: "CSV compatible revision" }
];

const THEME_PRESET_TOPICS = [
  "Renaissance et humanisme",
  "Révolution industrielle",
  "Énergie et transition écologique",
  "Citoyenneté numérique",
  "Probabilités et statistiques",
  "Argumentation en français"
];

const DIFFICULTY_OPTIONS: Array<{ value: string; label: string; hint: string }> = [
  { value: "easy", label: "Facile", hint: "Notions de base, questions directes." },
  { value: "medium", label: "Intermédiaire", hint: "Compréhension + application." },
  { value: "hard", label: "Avancé", hint: "Analyse, justification, mise en relation." }
];

const CLOZE_HOLE_PATTERN =
  /(?:_{2,}|\{\{\s*blank\s*\}\}|\[\s*blank\s*\]|\(\s*blank\s*\)|\{:MULTICHOICE:[^}]+\})/gi;

function stripQuestionPrefix(value: string): string {
  let next = value.trim();
  const patterns = [
    /^\s*item\s*#?\s*\d{1,3}\s*(?:[:.)-]\s*)/i,
    /^\s*q\s*#?\s*\d{1,3}\s*(?:[:.)-]\s*|\s+)/i,
    /^\s*question\s*(?:ouverte|open|qcm|a\s*saisir|numerique|texte\s*a\s*trous|association|choix\s*multiple|choix\s*unique)?\s*#?\s*\d{1,3}\s*(?:[:.)-]\s*|\s+)/i,
    /^\s*\d{1,3}\s*[:.)-]\s*/i
  ];

  let changed = true;
  while (changed) {
    changed = false;
    for (const pattern of patterns) {
      const cleaned = next.replace(pattern, "").trimStart();
      if (cleaned !== next) {
        next = cleaned;
        changed = true;
      }
    }
  }
  return next;
}

function stripTrailingCounter(value: string): string {
  return value.replace(/\s*[\[(]\s*\d{1,3}\s*[\])]\s*$/g, "").trim();
}

function normalizeAnswerText(value: string | undefined): string | undefined {
  if (!value) return value;
  const cleaned = stripTrailingCounter(value.replace(/^reponse\s*[:\-]\s*/i, "").trim());
  return cleaned;
}

function normalizeItemsForEditor(sourceItems: ContentItem[]): ContentItem[] {
  return sourceItems.map((item, index) => ({
    ...item,
    prompt: stripQuestionPrefix(item.prompt),
    correct_answer: normalizeAnswerText(item.correct_answer),
    distractors: item.distractors.map((entry) => stripTrailingCounter(entry)),
    position: Number.isFinite(item.position) ? item.position : index
  }));
}

function itemsNeedNormalization(sourceItems: ContentItem[], normalizedItems: ContentItem[]): boolean {
  if (sourceItems.length !== normalizedItems.length) return true;
  return sourceItems.some((item, index) => {
    const normalized = normalizedItems[index];
    if (!normalized) return true;
    if ((item.prompt ?? "") !== (normalized.prompt ?? "")) return true;
    if ((item.correct_answer ?? "") !== (normalized.correct_answer ?? "")) return true;
    if (item.distractors.length !== normalized.distractors.length) return true;
    return item.distractors.some((entry, dIndex) => entry !== normalized.distractors[dIndex]);
  });
}


function summarizePronoteXml(xml: string): {
  isLikelyPronote: boolean;
  totalQuestions: number;
  categoryCount: number;
  byType: Array<{ type: string; count: number }>;
} {
  const raw = xml.trim();
  if (!raw) {
    return { isLikelyPronote: false, totalQuestions: 0, categoryCount: 0, byType: [] };
  }

  const counts = new Map<string, number>();
  const matcher = /<question\b[^>]*type=["']([^"']+)["'][^>]*>/gi;
  for (const match of raw.matchAll(matcher)) {
    const type = (match[1] ?? "").trim().toLowerCase();
    if (!type) continue;
    counts.set(type, (counts.get(type) ?? 0) + 1);
  }

  const categoryCount = counts.get("category") ?? 0;
  const totalQuestions = Array.from(counts.entries()).reduce((sum, [type, count]) => {
    if (type === "category") return sum;
    return sum + count;
  }, 0);

  const byType = Array.from(counts.entries())
    .map(([type, count]) => ({ type, count }))
    .sort((a, b) => b.count - a.count || a.type.localeCompare(b.type));

  const isLikelyPronote = /<quiz[\s>]/i.test(raw) && totalQuestions > 0;
  return { isLikelyPronote, totalQuestions, categoryCount, byType };
}

type MatchingPair = { left: string; right: string };

export default function HomePage() {
  const [step, setStep] = useState<number>(1);
  const [token, setToken] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return sessionStorage.getItem("sb_token") ?? "";
    }
    return "";
  });
  const [projectId, setProjectId] = useState<string>("");
  const [sourceType, setSourceType] = useState<SourceType>("document");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [freeText, setFreeText] = useState<string>("");
  const [topic, setTopic] = useState<string>("");
  const [linkUrl, setLinkUrl] = useState<string>("");
  const [subject, setSubject] = useState<string>("");
  const [classLevel, setClassLevel] = useState<string>("");
  const [difficultyTarget, setDifficultyTarget] = useState<string>("medium");
  const [evaluationType, setEvaluationType] = useState<string>("");
  const [platform, setPlatform] = useState<string>("");
  const [learningGoal, setLearningGoal] = useState<string>("");
  const [sourceReviewText, setSourceReviewText] = useState<string>("");
  const [enableOcr, setEnableOcr] = useState<boolean>(false);
  const [enableTableExtraction, setEnableTableExtraction] = useState<boolean>(true);
  const [smartCleaning, setSmartCleaning] = useState<boolean>(true);
  const [sourceQuality, setSourceQuality] = useState<Record<string, unknown>>({});

  const [selectedTypes, setSelectedTypes] = useState<ContentType[]>([]);
  const [selectedPronoteModes, setSelectedPronoteModes] = useState<PronoteExerciseMode[]>(["single_choice"]);
  const [pronoteModeCounts, setPronoteModeCounts] = useState<Record<PronoteExerciseMode, number>>({
    single_choice: 10,
    multiple_choice: 5,
    numeric_value: 3,
    free_response: 3,
    spelling: 2,
    cloze_free: 3,
    cloze_list_unique: 3,
    cloze_list_variable: 3,
    matching: 5
  });
  const [matchingPairsPerQuestion, setMatchingPairsPerQuestion] = useState<number>(3);
  const [countPopup, setCountPopup] = useState<string | null>(null);
  const [generationCount, setGenerationCount] = useState<number>(10);
  const [instructions, setInstructions] = useState<string>("");
  const [contentSetId, setContentSetId] = useState<string>("");
  const [items, setItems] = useState<ContentItem[]>([]);
  const [qualityPreview, setQualityPreview] = useState<QualityPreview | null>(null);
  const [pronoteImportXml, setPronoteImportXml] = useState<string>("");
  const [pronoteImportFilename, setPronoteImportFilename] = useState<string>("import-pronote.xml");
  const [showPronoteImportPanel, setShowPronoteImportPanel] = useState<boolean>(false);
  const [replaceContentOnImport, setReplaceContentOnImport] = useState<boolean>(true);
  const [openEditorAfterImport, setOpenEditorAfterImport] = useState<boolean>(true);
  const [normalizeImportedItems, setNormalizeImportedItems] = useState<boolean>(true);
  const [importResult, setImportResult] = useState<PronoteImportResult | null>(null);
  const [analytics, setAnalytics] = useState<ProjectAnalytics | null>(null);

  const [exportFormat, setExportFormat] = useState<ExportFormat>("docx");
  const [pronoteShuffleAnswers, setPronoteShuffleAnswers] = useState<boolean>(true);
  const [downloadUrl, setDownloadUrl] = useState<string>("");

  const [jobProgress, setJobProgress] = useState<number>(0);
  const [busy, setBusy] = useState<boolean>(false);
  const [busyPhase, setBusyPhase] = useState<BusyPhase>(null);
  const [error, setError] = useState<string>("");
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [showAiReviewPopup, setShowAiReviewPopup] = useState<boolean>(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pronoteImportFileInputRef = useRef<HTMLInputElement | null>(null);

  // ── Item editor hook ──────────────────────────────────────
  const itemEditor = useItemEditor(items, setItems);

  const pronoteModeByValue = useMemo(
    () => new Map(PRONOTE_EXERCISE_OPTIONS.map((option) => [option.value, option])),
    []
  );

  const selectedPronoteOptions = useMemo(
    () =>
      selectedPronoteModes
        .map((mode) => pronoteModeByValue.get(mode))
        .filter(
          (
            option
          ): option is {
            value: PronoteExerciseMode;
            title: string;
            subtitle: string;
            contentType: ContentType;
            generationHint: string;
          } => Boolean(option)
        ),
    [pronoteModeByValue, selectedPronoteModes]
  );

  const selectedNonPronoteTypes = useMemo(
    () => selectedTypes.filter((value) => value !== "mcq"),
    [selectedTypes]
  );

  const selectedContentTypes = useMemo(() => {
    const pronoteTypes = selectedPronoteOptions.map((option) => option.contentType);
    return Array.from(new Set([...pronoteTypes, ...selectedNonPronoteTypes]));
  }, [selectedNonPronoteTypes, selectedPronoteOptions]);

  const pronoteRequestedCount = useMemo(
    () =>
      selectedPronoteModes.reduce((sum, mode) => {
        const next = pronoteModeCounts[mode];
        return sum + (Number.isFinite(next) ? Math.min(100, Math.max(1, next)) : 1);
      }, 0),
    [pronoteModeCounts, selectedPronoteModes]
  );

  const nonPronoteRequestedCount = useMemo(
    () => (selectedNonPronoteTypes.length > 0 ? selectedNonPronoteTypes.length * generationCount : 0),
    [generationCount, selectedNonPronoteTypes.length]
  );

  const requestedItemsBeforeCap = pronoteRequestedCount + nonPronoteRequestedCount;
  const requestedItemsTotal = Math.min(100, Math.max(1, requestedItemsBeforeCap || generationCount));
  const requestCountCapped = requestedItemsBeforeCap > 100;
  const selectedSourceOption = useMemo(
    () => SOURCE_OPTIONS.find((option) => option.value === sourceType) ?? SOURCE_OPTIONS[0],
    [sourceType]
  );
  const orderedSourceOptions = useMemo(() => {
    const active = SOURCE_OPTIONS.find((option) => option.value === sourceType);
    const others = SOURCE_OPTIONS.filter((option) => option.value !== sourceType);
    return active ? [active, ...others] : SOURCE_OPTIONS;
  }, [sourceType]);
  const pronoteImportSummary = useMemo(() => summarizePronoteXml(pronoteImportXml), [pronoteImportXml]);

  const canIngest = useMemo(() => {
    if (sourceType === "document") {
      return Boolean(selectedFile);
    }
    if (sourceType === "text") {
      return freeText.trim().length > 0;
    }
    if (sourceType === "theme") {
      return topic.trim().length > 0;
    }
    if (sourceType === "youtube") {
      return linkUrl.trim().length > 0;
    }
    return true;
  }, [sourceType, selectedFile, freeText, topic, linkUrl]);

  const isPdfSelected = useMemo(() => {
    if (!selectedFile) return false;
    return (
      selectedFile.type === "application/pdf" ||
      selectedFile.name.toLowerCase().endsWith(".pdf")
    );
  }, [selectedFile]);

  function updatePronoteModeCount(mode: PronoteExerciseMode, rawValue: string): void {
    const parsed = Number.parseInt(rawValue, 10);
    if (Number.isNaN(parsed)) {
      setPronoteModeCounts((current) => ({ ...current, [mode]: 1 }));
      return;
    }
    setPronoteModeCounts((current) => ({
      ...current,
      [mode]: Math.min(100, Math.max(1, parsed))
    }));
  }

  function togglePronoteMode(mode: PronoteExerciseMode): void {
    setSelectedPronoteModes((current) =>
      current.includes(mode) ? current.filter((value) => value !== mode) : [...current, mode]
    );
  }


  function selectFile(file: File | null): void {
    if (!file) {
      setSelectedFile(null);
      return;
    }

    if (file.size > MAX_UPLOAD_BYTES) {
      setSelectedFile(null);
      setError("Le fichier depasse 200MB");
      return;
    }

    setSelectedFile(file);
    setError("");
  }

  function openFilePicker(): void {
    fileInputRef.current?.click();
  }

  function handleFileInputChange(event: ChangeEvent<HTMLInputElement>): void {
    selectFile(event.target.files?.[0] ?? null);
  }

  async function loadPronoteXmlFile(file: File | null): Promise<void> {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".xml") && file.type !== "application/xml" && file.type !== "text/xml") {
      setError("Le fichier d'import doit etre un XML.");
      return;
    }
    try {
      const raw = await file.text();
      setPronoteImportFilename(file.name);
      setPronoteImportXml(raw);
      setError("");
    } catch {
      setError("Impossible de lire le fichier XML.");
    }
  }

  function openPronoteXmlPicker(): void {
    pronoteImportFileInputRef.current?.click();
  }

  function handlePronoteXmlFileInputChange(event: ChangeEvent<HTMLInputElement>): void {
    void loadPronoteXmlFile(event.target.files?.[0] ?? null);
  }

  function handleDropOnUploader(event: DragEvent<HTMLDivElement>): void {
    event.preventDefault();
    setIsDragOver(false);
    selectFile(event.dataTransfer.files?.[0] ?? null);
  }

  const {
    updateItem,
    addItem,
    removeItem,
    handleClozeAnswerChange,
    handleMatchingPairChange,
    handleMatchingAdd,
    handleMatchingRemove,
    handleChoiceToggle,
    handleChoiceTextChange,
    handleChoiceAdd,
    handleChoiceRemove,
    isChoiceQuestion,
    allowsMultipleCorrectAnswers,
    buildChoiceEditorState,
    splitExpectedAnswers,
    splitEditorList,
    countClozeHoles,
    parseMatchingPairsFromItem,
    dedupeChoiceValues,
  } = itemEditor;

  const {
    ensureAuthAndProject,
    loadSourceDocumentForReview,
    refreshQualityPreview,
    refreshAnalytics,
    handleIngest,
    handleGenerate,
    handleQuickPronoteGenerate,
    handleSaveContent,
    handleExport,
    handleSaveAndDownloadPronote,
    handleImportPronoteXml,
  } = useBusinessLogic({
    token, setToken, projectId, setProjectId,
    setBusy, setBusyPhase, setError, setJobProgress, setDownloadUrl, setStep,
    sourceType, selectedFile, freeText, topic, linkUrl,
    subject, setSubject, classLevel, setClassLevel,
    difficultyTarget, setDifficultyTarget, learningGoal, setLearningGoal,
    enableOcr, enableTableExtraction, smartCleaning, isPdfSelected,
    setSourceReviewText, sourceReviewText, setSourceQuality,
    setQualityPreview, setAnalytics,
    evaluationType, instructions,
    selectedPronoteOptions, selectedNonPronoteTypes,
    pronoteModeCounts, selectedPronoteModes, matchingPairsPerQuestion,
    pronoteRequestedCount, nonPronoteRequestedCount, generationCount,
    items, setItems, contentSetId, setContentSetId,
    exportFormat, setExportFormat, pronoteShuffleAnswers,
    pronoteImportXml, pronoteImportFilename,
    replaceContentOnImport, normalizeImportedItems, openEditorAfterImport,
    setImportResult, setShowPronoteImportPanel,
  });

  useEffect(() => {
    if (step === 4) {
      setShowAiReviewPopup(true);
    }
  }, [step]);

  const labelDifficulty = labelDifficultyUtil;
  const normalizeDifficultyValue = normalizeDifficultyValueUtil;
  const labelItemType = labelItemTypeUtil;
  const formatFileSize = formatFileSizeUtil;


  const busyLabel =
    busyPhase === "ingest"
      ? "Ingestion en cours..."
      : busyPhase === "generate"
        ? "Generation en cours..."
        : busyPhase === "save"
          ? "Sauvegarde en cours..."
          : "Traitement en cours...";

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-7 px-4 py-8 md:px-8">
      {busy && (busyPhase === "generate" || busyPhase === "export") && (
        <ConversionOverlay
          progress={jobProgress}
          phase={busyPhase}
          format={busyPhase === "export" ? exportFormat : undefined}
        />
      )}

      <section className="hero-shell animate-fadeInUp p-6 md:p-7">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-col gap-1">
            <Image
              src="/skillbeam-logo.png"
              alt="Logo SkillBeam"
              width={178}
              height={58}
              className="skillbeam-header-logo"
            />
            <p className="brand-title text-xs font-bold tracking-[0.18em] text-slate-400 uppercase pl-1">AI-édu Quiz</p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.25rem" }}>
            <span className="teacher-badge">Espace enseignant</span>
            <span style={{ fontSize: "0.7rem", color: "#94a3b8", fontFamily: "monospace" }}>v0.2.1</span>
          </div>
        </div>
        <p className="mb-5 max-w-3xl text-[1.2rem] font-semibold text-slate-800">
          Creez des exercices Pronote en 5 etapes.
        </p>
        <Stepper current={step} labels={STEP_LABELS} />
        <div className="hero-hints mt-5">
          <span className="hero-hint-chip">200 MB max</span>
          <span className="hero-hint-chip">1 a 100 questions</span>
          <span className="hero-hint-chip">Export direct</span>
        </div>
      </section>

      {error && <p className="status-error rounded-xl px-4 py-3 text-base">{error}</p>}

      {busy && busyPhase !== "export" && busyPhase !== "generate" && (
        <p className="status-info rounded-xl px-4 py-3 text-base">
          {busyLabel} progression: {jobProgress}%
        </p>
      )}

      {showPronoteImportPanel && (
        <section className="content-shell pronote-import-shell animate-fadeInUp p-6 md:p-7">
          <div className="pronote-import-header">
            <div className="pronote-import-title-wrap">
              <PronoteLogoIcon className="pronote-import-logo" />
              <div>
                <p className="pronote-import-kicker">Outil rapide Pronote</p>
                <h2 className="step-title pronote-import-title">Importer un XML Pronote existant</h2>
              </div>
            </div>
            <button type="button" className="ghost" onClick={() => setShowPronoteImportPanel(false)}>
              Fermer
            </button>
          </div>

          <p className="pronote-import-description">
            Importez un fichier XML Pronote, relisez les questions dans l&apos;éditeur puis re-exportez immédiatement.
          </p>

          <input
            ref={pronoteImportFileInputRef}
            type="file"
            className="hidden"
            accept=".xml,text/xml,application/xml"
            onChange={handlePronoteXmlFileInputChange}
          />

          <div className="pronote-import-grid">
            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-800">Nom du fichier</label>
              <input
                value={pronoteImportFilename}
                onChange={(e) => setPronoteImportFilename(e.target.value)}
                placeholder="import-pronote.xml"
              />
              <div className="pronote-import-file-actions">
                <button type="button" className="ghost" onClick={openPronoteXmlPicker}>
                  Charger un fichier XML
                </button>
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    setPronoteImportXml("");
                    setImportResult(null);
                  }}
                >
                  Vider
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold text-slate-800">Contenu XML Pronote</label>
              <textarea
                rows={9}
                value={pronoteImportXml}
                onChange={(e) => setPronoteImportXml(e.target.value)}
                placeholder="<?xml version='1.0' encoding='UTF-8' ?><quiz>...</quiz>"
              />
            </div>
          </div>

          <div className="pronote-import-options">
            <label className="pronote-import-option">
              <input
                type="checkbox"
                checked={replaceContentOnImport}
                onChange={(e) => setReplaceContentOnImport(e.target.checked)}
              />
              Remplacer le contenu actuel du projet
            </label>
            <label className="pronote-import-option">
              <input
                type="checkbox"
                checked={openEditorAfterImport}
                onChange={(e) => setOpenEditorAfterImport(e.target.checked)}
              />
              Ouvrir directement l&apos;édition après import
            </label>
            <label className="pronote-import-option">
              <input
                type="checkbox"
                checked={normalizeImportedItems}
                onChange={(e) => setNormalizeImportedItems(e.target.checked)}
              />
              Nettoyer les enoncés (supprimer Q1 / Item 1)
            </label>
          </div>

          <div className="pronote-import-insights">
            <div className="pronote-metric-card">
              <span className="pronote-metric-label">Questions détectées</span>
              <strong className="pronote-metric-value">{pronoteImportSummary.totalQuestions}</strong>
            </div>
            <div className="pronote-metric-card">
              <span className="pronote-metric-label">Bloc catégorie</span>
              <strong className="pronote-metric-value">{pronoteImportSummary.categoryCount}</strong>
            </div>
            <div className="pronote-metric-card">
              <span className="pronote-metric-label">Types trouvés</span>
              <strong className="pronote-metric-value">{pronoteImportSummary.byType.length}</strong>
            </div>
          </div>

          {pronoteImportSummary.byType.length > 0 && (
            <div className="pronote-type-list">
              {pronoteImportSummary.byType.map((entry) => (
                <span key={entry.type} className="pronote-type-chip">
                  {entry.type}: {entry.count}
                </span>
              ))}
            </div>
          )}

          {pronoteImportXml.trim().length > 0 && !pronoteImportSummary.isLikelyPronote && (
            <p className="mt-3 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              Le contenu semble incomplet. Verifiez que le XML contient bien une balise <code>&lt;quiz&gt;</code> et des
              balises <code>&lt;question type=&quot;...&quot;&gt;</code>.
            </p>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button type="button" className="ghost" onClick={() => setShowPronoteImportPanel(false)}>
              Retour
            </button>
            <button
              type="button"
              className="pronote-cta"
              onClick={handleImportPronoteXml}
              disabled={busy || !pronoteImportXml.trim()}
            >
              <PronoteLogoIcon className="pronote-logo-inline" />
              <span>Importer XML Pronote</span>
            </button>
            {importResult && (
              <span className="text-sm text-slate-700">
                Import reussi: <strong>{importResult.imported_items_count}</strong> item(s)
              </span>
            )}
          </div>
        </section>
      )}

      {step === 1 && (
        <section className="content-shell animate-fadeInUp p-6 md:p-7">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="step-title text-4xl text-slate-900">1. Choix de la source</h2>
            <div className="source-header-actions source-header-actions-inline">
              <button type="button" className="pronote-import-trigger" onClick={() => setShowPronoteImportPanel(true)}>
                <PronoteLogoIcon className="pronote-logo-inline" />
                <span>Importer XML Pronote</span>
              </button>
            </div>
          </div>
          <p className="source-toolbar-copy">Choisissez une source pour continuer.</p>

          <div className="source-grid">
            {SOURCE_OPTIONS.map((option) => (
              <Tile
                key={option.value}
                title={option.title}
                subtitle={option.subtitle}
                selected={sourceType === option.value}
                dimmed={sourceType !== null && sourceType !== option.value}
                icon={<span className="source-icon-badge">{option.badge}</span>}
                className={clsx(
                  "source-option-tile",
                  sourceType === option.value && "source-option-tile-selected"
                )}
                onClick={() => {
                  setSourceType(option.value);
                  setShowPronoteImportPanel(false);
                  setStep(2);
                }}
              />
            ))}
          </div>

        </section>
      )}

      {step === 2 && (
        <section className="content-shell animate-fadeInUp p-6 md:p-7">
          <h2 className="step-title mb-2 text-4xl text-slate-900">
            2. Ingestion source ({selectedSourceOption.title.toLowerCase()})
          </h2>
          <p className="mb-4 text-lg text-slate-700">Chargez ou saisissez votre contenu pédagogique.</p>

          {sourceType === "document" && (
            <div className="doc-upload-shell">
              <label className="text-[1.15rem] font-semibold text-slate-900">Fichier (max 200MB)</label>
              <div
                role="button"
                tabIndex={0}
                aria-label="Zone de depot de fichier"
                className={clsx("doc-dropzone", isDragOver && "is-drag-over", selectedFile && "has-file")}
                onClick={openFilePicker}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    openFilePicker();
                  }
                }}
                onDragOver={(event) => {
                  event.preventDefault();
                  setIsDragOver(true);
                }}
                onDragEnter={(event) => {
                  event.preventDefault();
                  setIsDragOver(true);
                }}
                onDragLeave={(event) => {
                  event.preventDefault();
                  setIsDragOver(false);
                }}
                onDrop={handleDropOnUploader}
              >
                <input
                  ref={fileInputRef}
                  className="hidden"
                  type="file"
                  onChange={handleFileInputChange}
                  accept=".pdf,.docx,.pptx,.txt,.md,.png,.jpg,.jpeg,application/pdf,text/plain,text/markdown,image/png,image/jpeg,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation"
                />
                <div className="doc-upload-icon" aria-hidden>
                  ↑
                </div>
                <p className="doc-upload-title">Deposez ou cliquez pour choisir un fichier</p>
                <p className="doc-upload-hint">PDF, DOCX, PPTX, TXT, MD</p>

                {selectedFile ? (
                  <div className="doc-file-chip">
                    <span className="doc-file-name">{selectedFile.name}</span>
                    <span className="doc-file-size">{formatFileSize(selectedFile.size)}</span>
                  </div>
                ) : (
                  <p className="doc-file-empty">Aucun fichier</p>
                )}
              </div>
            </div>
          )}

          {sourceType === "text" && (
            <div className="space-y-2">
              <label className="text-base font-medium text-slate-800">Texte source</label>
              <textarea rows={8} value={freeText} onChange={(e) => setFreeText(e.target.value)} />
            </div>
          )}

          {sourceType === "theme" && (
            <div className="theme-intake-shell">
              <div className="theme-intake-head">
                <div>
                  <p className="theme-intake-kicker">Mode guidé</p>
                  <h3 className="theme-intake-title">Construire un quiz à partir d&apos;une thématique</h3>
                  <p className="theme-intake-subtitle">
                    Renseignez le sujet, le niveau de classe et la difficulté. Vous pouvez ensuite lancer l&apos;ingestion.
                  </p>
                </div>
                <div className="theme-intake-steps">
                  <span className={clsx("theme-step-chip", topic.trim() && "is-done")}>1. Thématique</span>
                  <span className={clsx("theme-step-chip", classLevel.trim() && "is-done")}>2. Classe</span>
                  <span className={clsx("theme-step-chip", difficultyTarget.trim() && "is-done")}>3. Difficulté</span>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-2 md:col-span-2">
                  <label className="text-base font-semibold text-slate-800">Thématique</label>
                  <input
                    className="theme-main-input"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="Ex: Révolution industrielle"
                  />
                  <div className="theme-preset-row">
                    {THEME_PRESET_TOPICS.map((preset) => (
                      <button key={preset} type="button" className="theme-preset-chip" onClick={() => setTopic(preset)}>
                        {preset}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-base font-semibold text-slate-800">Matière</label>
                  <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Ex: Histoire-Géographie" />
                </div>
                <div className="space-y-2">
                  <label className="text-base font-semibold text-slate-800">Classe</label>
                  <select value={classLevel} onChange={(e) => setClassLevel(e.target.value)}>
                    <option value="">Sélectionner une classe</option>
                    {CLASS_LEVEL_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="space-y-2 md:col-span-2">
                  <label className="text-base font-semibold text-slate-800">Difficulté cible</label>
                  <div className="difficulty-card-grid">
                    {DIFFICULTY_OPTIONS.map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        className={clsx("difficulty-card", difficultyTarget === option.value && "is-active")}
                        onClick={() => setDifficultyTarget(option.value)}
                      >
                        <span className="difficulty-card-title">{option.label}</span>
                        <span className="difficulty-card-hint">{option.hint}</span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2 md:col-span-2">
                  <label className="text-base font-semibold text-slate-800">Objectif pédagogique (optionnel)</label>
                  <textarea
                    rows={3}
                    value={learningGoal}
                    onChange={(e) => setLearningGoal(e.target.value)}
                    placeholder="Ex: Évaluer la compréhension des causes et conséquences."
                  />
                </div>
              </div>
            </div>
          )}

          {sourceType === "youtube" && (
            <div className="space-y-2">
              <label className="text-base font-medium text-slate-800">URL</label>
              <input value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)} placeholder="https://..." />
              <p className="text-sm text-slate-600">
                La video doit exposer des sous-titres/captions exploitables. Sinon l&apos;ingestion echoue explicitement.
              </p>
            </div>
          )}

          {sourceType === "document" && (
            <div className="mt-4 rounded-xl border border-slate-200 bg-white/80 p-4">
              <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-slate-400">Options PDF avancées</p>

              {isPdfSelected ? (
                <div className="grid gap-2 sm:grid-cols-3">
                  {[
                    { label: "OCR auto", desc: "Reconnaissance de texte", checked: enableOcr, onChange: (v: boolean) => setEnableOcr(v) },
                    { label: "Extraction tableaux", desc: "Détecte les tableaux", checked: enableTableExtraction, onChange: (v: boolean) => setEnableTableExtraction(v) },
                    { label: "Nettoyage intelligent", desc: "Supprime les artefacts", checked: smartCleaning, onChange: (v: boolean) => setSmartCleaning(v) }
                  ].map(({ label, desc, checked, onChange }) => (
                    <label
                      key={label}
                      className={clsx(
                        "group flex cursor-pointer items-start gap-3 rounded-xl border-2 p-3 transition-all duration-200",
                        checked
                          ? "border-teal-500 bg-teal-50 shadow-[0_4px_12px_rgba(13,161,141,0.15)]"
                          : "border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50"
                      )}
                    >
                      <input type="checkbox" className="sr-only" checked={checked} onChange={(e) => onChange(e.target.checked)} />
                      <span className={clsx(
                        "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 transition-all duration-200",
                        checked ? "border-teal-500 bg-teal-500" : "border-slate-300 bg-white group-hover:border-teal-300"
                      )}>
                        {checked && (
                          <svg className="h-3 w-3 text-white" viewBox="0 0 12 12" fill="none">
                            <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        )}
                      </span>
                      <div>
                        <p className={clsx("text-sm font-semibold", checked ? "text-teal-800" : "text-slate-700")}>{label}</p>
                        <p className={clsx("text-xs", checked ? "text-teal-600" : "text-slate-400")}>{desc}</p>
                      </div>
                    </label>
                  ))}
                </div>
              ) : (
                <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                  Selectionnez un PDF.
                </div>
              )}
            </div>
          )}

          {Object.keys(sourceQuality).length > 0 && (
            <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50/70 p-4 text-sm text-slate-800">
              <p className="font-semibold text-emerald-900">Aperçu qualité source</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <div>Sections: <strong>{String(sourceQuality.sections ?? "-")}</strong></div>
                <div>Mots: <strong>{String(sourceQuality.word_count ?? "-")}</strong></div>
                <div>Tableaux détectés: <strong>{String(sourceQuality.table_candidates ?? 0)}</strong></div>
                <div>OCR: <strong>{String(sourceQuality.ocr_status ?? "n/a")}</strong></div>
              </div>
            </div>
          )}

          <div className="ingest-actions mt-5 flex flex-wrap gap-3">
            <button type="button" className="ghost ingest-btn" onClick={() => setStep(1)}>
              Retour
            </button>
            <button type="button" className="primary ingest-btn" onClick={handleIngest} disabled={!canIngest || busy}>
              Lancer ingestion
            </button>
          </div>
        </section>
      )}

      {step === 3 && (
        <section className="content-shell animate-fadeInUp p-6 md:p-7">
          <h2 className="step-title mb-2 text-4xl text-slate-900">3. Choix du contenu a generer</h2>
          <p className="mb-4 text-lg text-slate-700">Definissez le type d&apos;activites et le volume souhaite.</p>

          <div className="eval-type-section">
            <p className="eval-type-label"><span className="eval-step-badge">Étape 1</span> Type d&apos;évaluation</p>
            <div className="eval-type-grid">
              <button
                type="button"
                className={`eval-type-card eval-type-diagnostic ${evaluationType === "diagnostic" ? "is-selected" : ""}`}
                onClick={() => setEvaluationType(evaluationType === "diagnostic" ? "" : "diagnostic")}
              >
                <span className="eval-type-icon">🔍</span>
                <span className="eval-type-name">Diagnostique</span>
                <span className="eval-type-desc">Avant une séquence, tester le niveau des élèves</span>
              </button>
              <button
                type="button"
                className={`eval-type-card eval-type-formative ${evaluationType === "formative" ? "is-selected" : ""}`}
                onClick={() => setEvaluationType(evaluationType === "formative" ? "" : "formative")}
              >
                <span className="eval-type-icon">📊</span>
                <span className="eval-type-name">Formative</span>
                <span className="eval-type-desc">En cours de séquence, évaluer les compétences</span>
              </button>
              <button
                type="button"
                className={`eval-type-card eval-type-sommative ${evaluationType === "sommative" ? "is-selected" : ""}`}
                onClick={() => setEvaluationType(evaluationType === "sommative" ? "" : "sommative")}
              >
                <span className="eval-type-icon">🏆</span>
                <span className="eval-type-name">Sommative</span>
                <span className="eval-type-desc">Fin de séquence, valider les compétences acquises</span>
              </button>
            </div>
            {evaluationType && (
              <p className="eval-type-hint">
                {evaluationType === "diagnostic" && "\u2705 Pr\u00e9s\u00e9lection : QCM simples (choix unique + choix multiple) pour tester les pr\u00e9requis."}
                {evaluationType === "formative" && "\u2705 Pr\u00e9s\u00e9lection : mix progressif (QCM + saisie + texte \u00e0 trous) pour \u00e9valuer la compr\u00e9hension."}
                {evaluationType === "sommative" && "\u2705 Pr\u00e9s\u00e9lection : exercices vari\u00e9s et complets (QCM + saisie + trous + association) pour valider les comp\u00e9tences."}
              </p>
            )}
          </div>

          <div className={`eval-type-section ${!evaluationType ? "is-locked-light" : ""}`}>
            <p className="eval-type-label"><span className="eval-step-badge">Étape 2</span> Plateforme cible</p>
            <div className="eval-type-grid" style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
              <button
                type="button"
                className={`eval-type-card eval-type-diagnostic ${platform === "pronote" ? "is-selected" : ""}`}
                onClick={() => setPlatform(platform === "pronote" ? "" : "pronote")}
                disabled={!evaluationType}
              >
                <Image src="/pronote-logo.png" alt="Logo Pronote" width={120} height={40} className="eval-type-logo" />
                <span className="eval-type-name">Pronote</span>
                <span className="eval-type-desc">Exercices QCM, saisie, texte à trous, association</span>
              </button>
              <button
                type="button"
                className={`eval-type-card eval-type-sommative ${platform === "elea" ? "is-selected" : ""}`}
                onClick={() => setPlatform(platform === "elea" ? "" : "elea")}
                disabled={!evaluationType}
              >
                <Image src="/elea-logo.png" alt="Logo Éléa" width={180} height={60} className="eval-type-logo eval-type-logo-lg" />
                <span className="eval-type-desc">Activités pédagogiques à exporter vers Éléa/Moodle</span>
              </button>
            </div>
          </div>

          <div className={`eval-step2-section ${!platform ? "is-locked" : ""}`}>
            {!platform && (
              <div className="eval-step2-overlay">
                <span className="eval-step2-lock-msg">👆 Choisissez d&apos;abord la plateforme ci-dessus</span>
              </div>
            )}
            <p className="eval-type-label" style={{ marginBottom: "0.75rem" }}><span className="eval-step-badge">Étape 3</span> Type d&apos;exercices</p>

            {platform === "pronote" && (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {CONTENT_OPTIONS.filter((option) => option.value === "mcq").map((option) => {
                  const selected = selectedPronoteModes.length > 0;
                  return (
                    <Tile
                      key={option.value}
                      title={option.title}
                      subtitle={option.subtitle}
                      selected={selected}
                      variant="pronote"
                      icon={<PronoteLogoIcon />}
                      eyebrow="Creer facilement un QCM pour Pronote"
                      className="qcm-pronote-hero sm:col-span-2 lg:col-span-3"
                      extra={
                        <div
                          className="qcm-pronote-controls mt-1 rounded-xl border border-emerald-300 bg-white/70 p-3"
                          onClick={(event) => event.stopPropagation()}
                          onMouseDown={(event) => event.stopPropagation()}
                        >
                          <p className="mb-2 text-sm font-semibold text-emerald-900">Parcours simplifie Pronote</p>
                          <h4 className="pronote-panel-title">Types d&apos;exercices Pronote</h4>
                          <p className="mb-2 text-sm text-slate-700">
                            Uniquement les formats Pronote: choix unique, choix multiple, valeur numerique, reponse a saisir,
                            epellation et textes a trous.
                          </p>

                          <div className="pronote-family-grid">
                            {PRONOTE_EXERCISE_FAMILIES.map((family) => (
                              <div key={family.title} className="pronote-family-card">
                                <p className="pronote-family-title">{family.title}</p>
                                <p className="pronote-family-subtitle">{family.subtitle}</p>
                                <div className="pronote-choice-grid">
                                  {family.modes.map((mode) => {
                                    const option = pronoteModeByValue.get(mode);
                                    if (!option) {
                                      return null;
                                    }
                                    const checked = selectedPronoteModes.includes(mode);
                                    return (
                                      <button
                                        key={mode}
                                        type="button"
                                        className={clsx("pronote-choice-btn", checked && "is-selected")}
                                        onMouseDown={(event) => event.stopPropagation()}
                                        onClick={(event) => {
                                          event.stopPropagation();
                                          if (!checked) togglePronoteMode(mode);
                                          setCountPopup(mode);
                                        }}
                                      >
                                        <span className="pronote-choice-title">
                                          {checked ? "✓ " : ""}
                                          {option.title}
                                        </span>
                                        <span className="pronote-choice-subtitle">{option.subtitle}</span>
                                        {checked && (
                                          <span className="pronote-choice-badge">
                                            ×{pronoteModeCounts[mode] ?? 1}
                                            {mode === "matching" && ` · ${matchingPairsPerQuestion}p`}
                                          </span>
                                        )}
                                      </button>
                                    );
                                  })}
                                </div>
                              </div>
                            ))}
                          </div>

                          <p className="pronote-total mt-3">
                            Total questions Pronote&nbsp;: {pronoteRequestedCount} / 100
                            {selectedPronoteOptions.length > 0 && (
                              <span className="pronote-total-hint"> — cliquez sur un type pour configurer</span>
                            )}
                          </p>

                          {countPopup !== null && (() => {
                            const popupOption = pronoteModeByValue.get(countPopup as PronoteExerciseMode);
                            if (!popupOption) return null;
                            const popupChecked = selectedPronoteModes.includes(countPopup as PronoteExerciseMode);
                            const qCount = pronoteModeCounts[countPopup as PronoteExerciseMode] ?? 1;
                            const closePopup = () => setCountPopup(null);
                            return (
                              <div
                                className="pronote-popup-backdrop"
                                onClick={(event) => { event.stopPropagation(); closePopup(); }}
                                onMouseDown={(event) => event.stopPropagation()}
                                onKeyDown={(event) => { if (event.key === "Escape") closePopup(); }}
                                // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
                                tabIndex={-1}
                              >
                                <div
                                  className="pronote-popup"
                                  onClick={(event) => event.stopPropagation()}
                                  onMouseDown={(event) => event.stopPropagation()}
                                >
                                  <div className="pronote-popup-header">
                                    <div>
                                      <p className="pronote-popup-title">{popupOption.title}</p>
                                      <p className="pronote-popup-subtitle">{popupOption.subtitle}</p>
                                    </div>
                                    <button
                                      type="button"
                                      className="pronote-popup-close"
                                      onClick={(event) => { event.stopPropagation(); closePopup(); }}
                                    >
                                      ×
                                    </button>
                                  </div>

                                  <label className="pronote-popup-toggle">
                                    <input
                                      type="checkbox"
                                      checked={popupChecked}
                                      onChange={() => togglePronoteMode(countPopup as PronoteExerciseMode)}
                                    />
                                    Inclure ce type dans la génération
                                  </label>

                                  <div className="pronote-popup-fields">
                                    <div className="pronote-popup-field">
                                      <span>Nombre de questions</span>
                                      <div className="pronote-stepper">
                                        <button
                                          type="button"
                                          className="pronote-stepper-btn"
                                          onClick={() => updatePronoteModeCount(countPopup as PronoteExerciseMode, String(Math.max(1, qCount - 1)))}
                                          disabled={qCount <= 1}
                                        >−</button>
                                        <span className="pronote-stepper-value">{qCount}</span>
                                        <button
                                          type="button"
                                          className="pronote-stepper-btn"
                                          onClick={() => updatePronoteModeCount(countPopup as PronoteExerciseMode, String(Math.min(100, qCount + 1)))}
                                          disabled={qCount >= 100}
                                        >+</button>
                                      </div>
                                    </div>
                                    {countPopup === "matching" && (
                                      <div className="pronote-popup-field">
                                        <span>Paires par question</span>
                                        <div className="pronote-stepper">
                                          <button
                                            type="button"
                                            className="pronote-stepper-btn"
                                            onClick={() => setMatchingPairsPerQuestion((p) => Math.max(2, p - 1))}
                                            disabled={matchingPairsPerQuestion <= 2}
                                          >−</button>
                                          <span className="pronote-stepper-value">{matchingPairsPerQuestion}</span>
                                          <button
                                            type="button"
                                            className="pronote-stepper-btn"
                                            onClick={() => setMatchingPairsPerQuestion((p) => Math.min(6, p + 1))}
                                            disabled={matchingPairsPerQuestion >= 6}
                                          >+</button>
                                        </div>
                                      </div>
                                    )}
                                  </div>

                                  <button
                                    type="button"
                                    className="pronote-popup-confirm"
                                    onClick={(event) => { event.stopPropagation(); closePopup(); }}
                                  >
                                    ✓ Confirmer
                                  </button>
                                </div>
                              </div>
                            );
                          })()}

                          <div className="mt-3 grid gap-3 sm:grid-cols-2 sm:items-end">
                            <label className="text-sm font-medium text-slate-800">
                              Niveau de difficulte
                              <select value={difficultyTarget} onChange={(e) => setDifficultyTarget(e.target.value)}>
                                <option value="easy">Facile</option>
                                <option value="medium">Intermediaire</option>
                                <option value="hard">Avance</option>
                              </select>
                            </label>
                            <div className="flex justify-end">
                              <button
                                type="button"
                                className="primary"
                                onMouseDown={(event) => event.stopPropagation()}
                                onClick={async (event) => {
                                  event.stopPropagation();
                                  await handleQuickPronoteGenerate();
                                }}
                                disabled={busy || selectedPronoteModes.length === 0 || !evaluationType}
                              >
                                {`Generer exercices Pronote (${pronoteRequestedCount})`}
                              </button>
                            </div>
                          </div>
                        </div>
                      }
                      onClick={() => {
                        setSelectedPronoteModes((current) => (current.length > 0 ? [] : ["single_choice"]));
                      }}
                    />
                  );
                })}
              </div>
            )}

            {platform === "elea" && (
              <div className="elea-space">
                <div className="elea-space-head">
                  <div className="elea-space-title-wrap">
                    <EleaLogoIcon className="elea-logo-inline" />
                    <div>
                      <p className="elea-space-label">Espace Éléa</p>
                      <p className="elea-space-subtitle">Activités pédagogiques à exporter vers Éléa/Moodle</p>
                    </div>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {CONTENT_OPTIONS.filter((option) => option.value !== "mcq").map((option) => {
                    const selected = selectedTypes.includes(option.value);
                    return (
                      <Tile
                        key={option.value}
                        title={option.title}
                        subtitle={option.subtitle}
                        selected={selected}
                        dimmed={selectedTypes.length > 0 && !selected}
                        className="elea-tile"
                        onClick={() => {
                          setSelectedTypes((current) =>
                            current.includes(option.value)
                              ? current.filter((v) => v !== option.value)
                              : [...current, option.value]
                          );
                        }}
                      />
                    );
                  })}
                </div>
                <div className="elea-brand">
                  <EleaLogoIcon className="elea-logo-large" />
                  <p className="elea-brand-name">Éléa</p>
                </div>
              </div>
            )}
          </div>

          <div className={clsx("mt-4 grid gap-3", selectedPronoteModes.length > 0 ? "md:grid-cols-2" : "md:grid-cols-3")}>
            <div className="space-y-2">
              <label className="text-base font-medium text-slate-800">Matiere</label>
              <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="ex: Anglais" />
            </div>
            <div className="space-y-2">
              <label className="text-base font-medium text-slate-800">Classe</label>
              <select value={classLevel} onChange={(e) => setClassLevel(e.target.value)}>
                <option value="">Sélectionner une classe</option>
                {CLASS_LEVEL_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </div>
            {selectedPronoteModes.length === 0 && (
              <div className="space-y-2">
                <label className="text-base font-medium text-slate-800">Difficulté cible</label>
                <select value={difficultyTarget} onChange={(e) => setDifficultyTarget(e.target.value)}>
                  <option value="easy">Facile</option>
                  <option value="medium">Intermediaire</option>
                  <option value="hard">Avance</option>
                </select>
              </div>
            )}
          </div>

          <div className="mt-4 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <label className="text-base font-medium text-slate-800">
                Texte source relu avant generation (modifiable)
              </label>
              <button
                type="button"
                className="ghost"
                onClick={async () => {
                  try {
                    const { authToken, project } = await ensureAuthAndProject();
                    await loadSourceDocumentForReview(authToken, project);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Impossible de recharger le texte source");
                  }
                }}
                disabled={busy}
              >
                Recharger depuis ingestion
              </button>
            </div>
            <textarea
              rows={8}
              value={sourceReviewText}
              onChange={(e) => setSourceReviewText(e.target.value)}
              placeholder="Le texte extrait/synthetise apparait ici pour relecture avant generation."
            />
            <p className="text-sm text-slate-600">
              Ce texte est celui envoye au LLM. Vous pouvez corriger, simplifier ou enrichir avant de generer.
            </p>
          </div>

          {selectedNonPronoteTypes.length > 0 && (
            <div className="mt-4 space-y-2">
              <label className="text-base font-medium text-slate-800">
                Nombre d&apos;items par type (hors Pronote) (1-100)
              </label>
              <input
                type="number"
                min={1}
                max={100}
                value={generationCount}
                onChange={(e) => {
                  const parsed = Number.parseInt(e.target.value, 10);
                  if (Number.isNaN(parsed)) {
                    setGenerationCount(1);
                    return;
                  }
                  setGenerationCount(Math.min(100, Math.max(1, parsed)));
                }}
              />
            </div>
          )}

          <div className="mt-4 rounded-xl border border-slate-200 bg-white/70 px-4 py-3 text-sm text-slate-700">
            Total demande selon vos choix: <strong>{requestedItemsTotal}</strong> item(s)
            {requestCountCapped && " (plafonne a 100 par generation)."}
          </div>

          <div className="mt-4 space-y-2">
            <label className="text-base font-medium text-slate-800">Instructions supplementaires (optionnel)</label>
            <textarea
              rows={4}
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Ex: Niveau BTS, 10 QCM, feedback court."
            />
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            <button type="button" className="ghost" onClick={() => setStep(2)}>
              Retour
            </button>
            <button type="button" className="primary" onClick={handleGenerate} disabled={selectedContentTypes.length === 0 || busy || !evaluationType}>
              Generer
            </button>
          </div>
        </section>
      )}

      {step === 4 && (
        <section className="content-shell animate-fadeInUp p-6 md:p-7">
          <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="step-title mb-2 text-4xl text-slate-900">4. Edition humaine</h2>
              <p className="text-lg text-slate-700">Relisez, corrigez et adaptez les questions avant export.</p>
            </div>
            <Image src="/skillbeam-logo.png" alt="Logo SkillBeam" width={190} height={62} className="skillbeam-inline-logo" />
          </div>
          <div className="mb-3 flex flex-wrap items-center gap-2 rounded-xl border border-slate-300 bg-slate-50 px-4 py-3">
            <span className="answer-chip answer-chip-good">Bonne reponse (vert)</span>
            <span className="answer-chip answer-chip-bad">Mauvaise reponse (rouge)</span>
          </div>

          <div className="mb-4 rounded-xl border border-slate-200 bg-white/80 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-base font-semibold text-slate-900">Qualité pédagogique avant export</p>
              <button
                type="button"
                className="ghost"
                onClick={async () => {
                  try {
                    const { authToken, project } = await ensureAuthAndProject();
                    await refreshQualityPreview(authToken, project);
                  } catch (e) {
                    setError(e instanceof Error ? e.message : "Impossible de recalculer la qualité");
                  }
                }}
                disabled={busy}
              >
                Recalculer
              </button>
            </div>
            {qualityPreview ? (
              <div className="mt-3 space-y-2">
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <span className="rounded-full bg-slate-100 px-3 py-1">
                    Score global: <strong>{qualityPreview.overall_score}/100</strong>
                  </span>
                  <span
                    className={clsx(
                      "rounded-full px-3 py-1",
                      qualityPreview.readiness === "ready" && "bg-emerald-100 text-emerald-900",
                      qualityPreview.readiness === "review_needed" && "bg-amber-100 text-amber-900",
                      qualityPreview.readiness === "blocked" && "bg-rose-100 text-rose-900"
                    )}
                  >
                    Etat:{" "}
                    {qualityPreview.readiness === "ready"
                      ? "pret"
                      : qualityPreview.readiness === "review_needed"
                        ? "a revoir"
                        : "bloque"}
                  </span>
                </div>
                {qualityPreview.issues.length > 0 ? (
                  <ul className="space-y-1 text-sm text-slate-700">
                    {qualityPreview.issues.slice(0, 8).map((issue, idx) => (
                      <li key={`${issue.code}-${idx}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                        <span className="font-semibold uppercase">{issue.severity}</span>: {issue.message}
                        {issue.item_index ? ` (item ${issue.item_index})` : ""}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm text-emerald-700">Aucune alerte majeure detectee.</p>
                )}
              </div>
            ) : (
              <p className="mt-2 text-sm text-slate-600">Lancez un calcul de qualité pour afficher l&apos;aperçu.</p>
            )}
          </div>

          <div className="space-y-3">
            {items.map((item, index) => (
              (() => {
                const choiceQuestion = isChoiceQuestion(item);
                const allowMultiple = allowsMultipleCorrectAnswers(item);
                const choiceEditor = buildChoiceEditorState(item);
                const isClozeQuestion = item.item_type === "cloze";
                const isMatchingQuestion = item.item_type === "matching";
                const clozeAnswers = isClozeQuestion ? buildClozeExpectedAnswers(item) : [];
                const clozeHoleCount = isClozeQuestion ? Math.max(1, countClozeHoles(item.prompt)) : 0;
                const clozeHasChoicePool =
                  isClozeQuestion &&
                  (item.tags.some((tag) => ["cloze_list_unique", "cloze_list_variable"].includes(tag.toLowerCase())) ||
                    item.answer_options.length > 0 ||
                    item.distractors.length > 0);
                const clozeChoicePool = isClozeQuestion
                  ? dedupeChoiceValues([...item.answer_options, ...item.distractors])
                  : [];
                const matchingPairs = isMatchingQuestion ? parseMatchingPairsFromItem(item) : [];

                return (
                  <article key={item.id} className="editor-item p-5">
                    <div className="editor-item-header mb-3">
                      <div className="editor-item-heading">
                        <strong className="editor-item-index">Item #{index + 1}</strong>
                        <span className="editor-item-type">Type de question: {labelItemType(item)}</span>
                      </div>
                      <button type="button" className="ghost" onClick={() => removeItem(index)}>
                        Supprimer
                      </button>
                    </div>

                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="md:col-span-2">
                        <label className="editor-label">Enonce</label>
                        <textarea
                          className="editor-prompt-input"
                          rows={4}
                          value={item.prompt}
                          onChange={(e) => updateItem(index, { prompt: e.target.value })}
                        />
                      </div>
                      <div>
                        <label className="editor-label">Difficulte</label>
                        <select
                          value={normalizeDifficultyValue(item.difficulty)}
                          onChange={(e) => updateItem(index, { difficulty: e.target.value })}
                        >
                          <option value="easy">Facile</option>
                          <option value="medium">Intermediaire</option>
                          <option value="hard">Avance</option>
                        </select>
                      </div>
                    </div>

                    {choiceQuestion ? (
                      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50/70 p-3">
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-slate-800">
                            Reponses (cochez {allowMultiple ? "les bonnes reponses" : "la bonne reponse"})
                          </p>
                          <button type="button" className="ghost" onClick={() => handleChoiceAdd(index, item)}>
                            Ajouter reponse
                          </button>
                        </div>
                        <div className="space-y-2">
                          {choiceEditor.choices.map((choice, choiceIndex) => {
                            const key = choice.trim().toLowerCase();
                            const checked = key.length > 0 && choiceEditor.correctKeys.has(key);
                            return (
                              <div
                                key={`${item.id}-choice-${choiceIndex}`}
                                className={clsx("editor-choice-row", checked ? "is-correct" : "is-distractor")}
                              >
                                <label className="editor-choice-check">
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={(e) => handleChoiceToggle(index, item, choiceIndex, e.target.checked)}
                                  />
                                  <span>{checked ? "Bonne reponse" : "Distracteur"}</span>
                                </label>
                                <input
                                  className={checked ? "answer-input-good" : "answer-input-bad"}
                                  value={choice}
                                  onChange={(e) => handleChoiceTextChange(index, item, choiceIndex, e.target.value)}
                                />
                                <button type="button" className="ghost" onClick={() => handleChoiceRemove(index, item, choiceIndex)}>
                                  Retirer
                                </button>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : isClozeQuestion ? (
                      <div className="mt-3 space-y-3 rounded-xl border border-slate-200 bg-slate-50/70 p-3">
                        <p className="text-sm font-semibold text-slate-800">
                          Reponses attendues pour texte a trous: 1 mot/groupe de mots par trou detecte
                          ({clozeHoleCount} trou{clozeHoleCount > 1 ? "s" : ""})
                        </p>
                        <div className="grid gap-2 md:grid-cols-2">
                          {clozeAnswers.map((answer, answerIndex) => (
                            <div key={`${item.id}-cloze-${answerIndex}`}>
                              <label className="editor-label editor-label-good">Trou {answerIndex + 1}</label>
                              <input
                                className="answer-input-good"
                                value={answer}
                                onChange={(e) => handleClozeAnswerChange(index, item, answerIndex, e.target.value)}
                              />
                            </div>
                          ))}
                        </div>
                        {clozeHasChoicePool && (
                          <div>
                            <label className="editor-label editor-label-bad">
                              Banque de mots (liste unique/variable, separes par ; )
                            </label>
                            <textarea
                              rows={2}
                              className="answer-input-bad"
                              value={clozeChoicePool.join(" ; ")}
                              onChange={(e) => {
                                const nextChoices = splitEditorList(e.target.value);
                                updateItem(index, {
                                  distractors: nextChoices,
                                  answer_options: nextChoices
                                });
                              }}
                            />
                          </div>
                        )}
                      </div>
                    ) : isMatchingQuestion ? (
                      <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50/70 p-3">
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-semibold text-slate-800">
                            Paires a associer (phrases completes, pas mots isoles)
                          </p>
                          <button type="button" className="ghost" onClick={() => handleMatchingAdd(index, item)}>
                            Ajouter une paire
                          </button>
                        </div>
                        <div className="space-y-2">
                          {matchingPairs.map((pair, pairIndex) => (
                            <div key={`${item.id}-pair-${pairIndex}`} className="grid gap-2 md:grid-cols-[1fr_1fr_auto]">
                              <input
                                className="answer-input-good"
                                value={pair.left}
                                onChange={(e) => handleMatchingPairChange(index, item, pairIndex, "left", e.target.value)}
                                placeholder="Concept en 2 a 6 mots (ex: Commutation de paquets)"
                              />
                              <input
                                className="answer-input-good"
                                value={pair.right}
                                onChange={(e) => handleMatchingPairChange(index, item, pairIndex, "right", e.target.value)}
                                placeholder="Definition complete en phrase (ex: Methode de transmission qui segmente les donnees en paquets)"
                              />
                              <button type="button" className="ghost" onClick={() => handleMatchingRemove(index, item, pairIndex)}>
                                Retirer
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="mt-3 grid gap-2 md:grid-cols-3">
                        <div className="md:col-span-1">
                          <label className="editor-label editor-label-good">Bonne reponse</label>
                          <input
                            className="answer-input-good"
                            value={item.correct_answer ?? ""}
                            onChange={(e) => updateItem(index, { correct_answer: e.target.value })}
                          />
                        </div>
                        {item.distractors.map((distractor, dIndex) => (
                          <div key={`${item.id}-d-${dIndex}`}>
                            <label className="editor-label editor-label-bad">Distracteur {dIndex + 1}</label>
                            <input
                              className="answer-input-bad"
                              value={distractor}
                              onChange={(e) => {
                                const next = [...item.distractors];
                                next[dIndex] = e.target.value;
                                updateItem(index, { distractors: next });
                              }}
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  </article>
                );
              })()
            ))}
          </div>

          {selectedPronoteModes.length > 0 && (
            <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50/70 px-4 py-3">
              <label className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-emerald-900">
                <input
                  type="checkbox"
                  checked={pronoteShuffleAnswers}
                  onChange={(e) => setPronoteShuffleAnswers(e.target.checked)}
                />
                Melanger l&apos;ordre des reponses dans le XML Pronote (bonne reponse pas toujours en premier)
              </label>
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-3">
            <button type="button" className="ghost" onClick={addItem}>
              Ajouter item
            </button>
            <button type="button" className="ghost" onClick={() => setStep(3)}>
              Retour
            </button>
            {selectedPronoteModes.length > 0 && (
              <button
                type="button"
                className="pronote-cta"
                onClick={handleSaveAndDownloadPronote}
                disabled={busy || items.length === 0}
              >
                <PronoteLogoIcon className="pronote-logo-inline" />
                <span>Telecharger fichier PRONOTE</span>
              </button>
            )}
            <button type="button" className="primary" onClick={handleSaveContent} disabled={busy || items.length === 0}>
              Valider les modifications
            </button>
          </div>
          <button
            type="button"
            className="ai-review-banner mt-3"
            onClick={() => setShowAiReviewPopup(true)}
          >
            <span className="ai-review-banner-icon">&#9888;&#65039;</span>
            <span className="ai-review-banner-text">
              <span className="ai-review-banner-title">Relecture recommandée</span>
              <span className="ai-review-banner-subtitle">
                Contenu généré par IA — cliquez pour consulter la proposition et valider
              </span>
            </span>
            <span className="ai-review-banner-arrow">→</span>
          </button>

          <AiReviewPopup open={showAiReviewPopup} onClose={() => setShowAiReviewPopup(false)} />
        </section>
      )}

      {step === 5 && (
        <section className="content-shell animate-fadeInUp p-6 md:p-7">
          <h2 className="step-title mb-2 text-4xl text-slate-900">5. Export</h2>
          <p className="mb-4 text-lg text-slate-700">Choisissez le format de diffusion et telechargez le fichier.</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {EXPORT_OPTIONS.map((option) => {
              const pronote = option.value === "pronote_xml";
              return (
                <Tile
                  key={option.value}
                  title={option.title}
                  subtitle={option.subtitle}
                  selected={exportFormat === option.value}
                  onClick={() => setExportFormat(option.value)}
                  variant={pronote ? "pronote" : "default"}
                  icon={pronote ? <PronoteLogoIcon /> : undefined}
                />
              );
            })}
          </div>

          {exportFormat === "pronote_xml" && (
            <>
              <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50/70 px-4 py-3">
                <label className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-emerald-900">
                  <input
                    type="checkbox"
                    checked={pronoteShuffleAnswers}
                    onChange={(e) => setPronoteShuffleAnswers(e.target.checked)}
                  />
                  Melanger l&apos;ordre des reponses dans le XML Pronote (bonne reponse pas toujours en premier)
                </label>
              </div>
              <button
                type="button"
                className="ai-review-banner mt-3"
                onClick={() => setShowAiReviewPopup(true)}
              >
                <span className="ai-review-banner-icon">&#9888;&#65039;</span>
                <span className="ai-review-banner-text">
                  <span className="ai-review-banner-title">Relecture recommandée</span>
                  <span className="ai-review-banner-subtitle">
                    Contenu généré par IA — cliquez pour consulter la proposition et valider
                  </span>
                </span>
                <span className="ai-review-banner-arrow">→</span>
              </button>

              <AiReviewPopup open={showAiReviewPopup} onClose={() => setShowAiReviewPopup(false)} />
            </>
          )}

          <div className="mt-4 flex flex-wrap gap-3">
            <button type="button" className="ghost" onClick={() => setStep(4)}>
              Retour
            </button>
            <button
              type="button"
              className="primary"
              onClick={handleExport}
              disabled={busy || qualityPreview?.readiness === "blocked"}
            >
              Exporter
            </button>
            <button
              type="button"
              className="ghost"
              onClick={async () => {
                try {
                  const { authToken, project } = await ensureAuthAndProject();
                  await refreshAnalytics(authToken, project);
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Impossible de charger les analytics");
                }
              }}
              disabled={busy}
            >
              Rafraichir analytics
            </button>
          </div>

          {qualityPreview?.readiness === "blocked" && (
            <p className="mt-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
              Export bloque: corrigez les points critiques dans l&apos;etape Edition humaine.
            </p>
          )}

          {analytics && (
            <div className="mt-4 rounded-xl border border-slate-200 bg-white/80 p-4 text-sm text-slate-800">
              <p className="font-semibold text-slate-900">Analytics projet</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                <div>Items totaux: <strong>{analytics.total_items}</strong></div>
                <div>Versions banque: <strong>{analytics.question_bank_versions}</strong></div>
                <div>Imports Pronote: <strong>{analytics.pronote_import_runs}</strong></div>
                <div>Dernier content_set: <strong>{analytics.latest_content_set_id ?? "-"}</strong></div>
              </div>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                <div>
                  <p className="font-semibold text-slate-700">Par type</p>
                  {Object.entries(analytics.by_item_type).map(([key, value]) => (
                    <p key={key}>
                      {key}: <strong>{value}</strong>
                    </p>
                  ))}
                </div>
                <div>
                  <p className="font-semibold text-slate-700">Par difficulte</p>
                  {Object.entries(analytics.by_difficulty).map(([key, value]) => (
                    <p key={key}>
                      {labelDifficulty(key)}: <strong>{value}</strong>
                    </p>
                  ))}
                </div>
                <div>
                  <p className="font-semibold text-slate-700">Exports</p>
                  {Object.entries(analytics.export_by_format).map(([key, value]) => (
                    <p key={key}>
                      {key}: <strong>{value}</strong>
                    </p>
                  ))}
                </div>
              </div>
            </div>
          )}

          {downloadUrl && (
            <p className="status-success mt-4 rounded-xl px-4 py-3 text-base">
              Export pret:{" "}
              <a className="underline" href={downloadUrl} download>
                telecharger l&apos;artefact
              </a>
            </p>
          )}
        </section>
      )}
    </main>
  );
}
