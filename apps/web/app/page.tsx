"use client";

import clsx from "clsx";
import Image from "next/image";
import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { ConversionOverlay } from "@/components/conversion-overlay";
import { Stepper } from "@/components/stepper";
import { Tile } from "@/components/tile";
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
type BusyPhase = "ingest" | "generate" | "save" | "export" | null;
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

type PronoteExerciseMode =
  | "single_choice"
  | "multiple_choice"
  | "numeric_value"
  | "free_response"
  | "spelling"
  | "cloze_free"
  | "cloze_list_unique"
  | "cloze_list_variable"
  | "matching";

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

function PronoteLogoIcon({ className }: { className?: string }) {
  return (
    <Image
      src="/pronote-logo.png"
      alt="Logo Pronote"
      width={56}
      height={56}
      className={clsx("pronote-logo-img", className)}
    />
  );
}

function EleaLogoIcon({ className }: { className?: string }) {
  return <Image src="/elea-logo.png" alt="Logo Elea" width={340} height={107} className={className} />;
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
  const [token, setToken] = useState<string>("");
  const [projectId, setProjectId] = useState<string>("");
  const [sourceType, setSourceType] = useState<SourceType>("document");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [freeText, setFreeText] = useState<string>("");
  const [topic, setTopic] = useState<string>("");
  const [linkUrl, setLinkUrl] = useState<string>("");
  const [subject, setSubject] = useState<string>("");
  const [classLevel, setClassLevel] = useState<string>("");
  const [difficultyTarget, setDifficultyTarget] = useState<string>("medium");
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
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pronoteImportFileInputRef = useRef<HTMLInputElement | null>(null);

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

  function formatFileSize(sizeBytes: number): string {
    if (sizeBytes < 1024) {
      return `${sizeBytes} o`;
    }
    if (sizeBytes < 1024 * 1024) {
      return `${(sizeBytes / 1024).toFixed(1)} Ko`;
    }
    return `${(sizeBytes / (1024 * 1024)).toFixed(1)} Mo`;
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

  async function ensureAuthAndProject(): Promise<{ authToken: string; project: string }> {
    let authToken = token;
    if (!authToken) {
      const auth = await login("demo@skillbeam.local", "demo123");
      authToken = auth.access_token;
      setToken(authToken);
    }

    let project = projectId;
    if (!project) {
      const created = await createProject(authToken, "Projet Wizard");
      project = created.id;
      setProjectId(project);
    }

    return { authToken, project };
  }

  async function refreshQualityPreview(authToken: string, project: string): Promise<void> {
    try {
      const preview = await getQualityPreview(authToken, project);
      setQualityPreview(preview);
    } catch (e) {
      setQualityPreview(null);
      setError(e instanceof Error ? e.message : "Impossible de calculer la qualité pédagogique");
    }
  }

  async function refreshAnalytics(authToken: string, project: string): Promise<void> {
    try {
      const data = await getProjectAnalytics(authToken, project);
      setAnalytics(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Impossible de charger les analytics");
    }
  }

  async function loadSourceDocumentForReview(authToken: string, project: string): Promise<void> {
    const document = await getSourceDocument(authToken, project);
    setSourceReviewText(document.plain_text);

    const metadata = document.metadata ?? {};
    const quality = metadata.source_quality;
    if (quality && typeof quality === "object" && !Array.isArray(quality)) {
      setSourceQuality(quality as Record<string, unknown>);
    } else {
      setSourceQuality({});
    }
    if (!subject && typeof metadata.subject === "string" && metadata.subject.trim()) {
      setSubject(metadata.subject.trim());
    }
    if (
      typeof metadata.class_level === "string" &&
      metadata.class_level.trim() &&
      CLASS_LEVEL_OPTIONS.includes(metadata.class_level.trim())
    ) {
      setClassLevel(metadata.class_level.trim());
    }
    if (typeof metadata.difficulty_target === "string" && metadata.difficulty_target.trim()) {
      setDifficultyTarget(metadata.difficulty_target.trim().toLowerCase());
    }
    if (!learningGoal && typeof metadata.learning_goal === "string" && metadata.learning_goal.trim()) {
      setLearningGoal(metadata.learning_goal.trim());
    }
  }

  async function handleIngest() {
    setBusy(true);
    setBusyPhase("ingest");
    setError("");
    setDownloadUrl("");
    setJobProgress(0);

    try {
      const { authToken, project } = await ensureAuthAndProject();
      let sourceAssetId: string | undefined;

      if (sourceType === "document") {
        if (!selectedFile) {
          throw new Error("Document requis");
        }
        if (selectedFile.size > MAX_UPLOAD_BYTES) {
          throw new Error("Le fichier depasse 200MB");
        }

        const init = await initSource(authToken, project, {
          source_type: sourceType,
          filename: selectedFile.name,
          mime_type: selectedFile.type,
          size_bytes: selectedFile.size,
          enable_ocr: isPdfSelected ? enableOcr : false,
          enable_table_extraction: isPdfSelected ? enableTableExtraction : false,
          smart_cleaning: isPdfSelected ? smartCleaning : false
        });
        sourceAssetId = init.asset_id;
        if (!init.upload_url) {
          throw new Error("URL upload manquante");
        }
        await uploadToPresigned(init.upload_url, selectedFile);
      } else {
        const init = await initSource(authToken, project, {
          source_type: sourceType,
          raw_text: sourceType === "text" ? freeText : undefined,
          topic: sourceType === "theme" ? topic : undefined,
          link_url: sourceType === "youtube" ? linkUrl : undefined,
          subject: subject.trim() || undefined,
          class_level: classLevel.trim() || undefined,
          difficulty_target: difficultyTarget.trim() || undefined,
          learning_goal: learningGoal.trim() || undefined
        });
        sourceAssetId = init.asset_id;
      }

      const ingest = await launchIngest(authToken, project, sourceAssetId);
      const job = await pollJobUntilDone(authToken, ingest.job_id, (next) => setJobProgress(next.progress));
      setJobProgress(job.progress);
      await loadSourceDocumentForReview(authToken, project);
      setStep(3);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur ingestion");
    } finally {
      setBusy(false);
      setBusyPhase(null);
    }
  }

  function buildGenerationPlan(options?: { pronoteOnly?: boolean }): {
    contentTypes: ContentType[];
    maxItems: number;
    instructions?: string;
  } {
    const pronoteOnly = options?.pronoteOnly ?? false;
    const activePronoteOptions = selectedPronoteOptions;
    const pronoteTypes = activePronoteOptions.map((option) => option.contentType);
    const baseTypes = pronoteOnly ? [] : selectedNonPronoteTypes;
    const contentTypes = Array.from(new Set([...pronoteTypes, ...baseTypes]));

    const pronoteDistribution = activePronoteOptions
      .map((option) => `- ${option.title}: ${Math.min(100, Math.max(1, pronoteModeCounts[option.value] ?? 1))}`)
      .join("\n");
    const pronoteHints = activePronoteOptions.map((option) => `- ${option.title}: ${option.generationHint}`).join("\n");
    const pronoteModeJson = activePronoteOptions.reduce<Record<string, number>>((acc, option) => {
      acc[option.value] = Math.min(100, Math.max(1, pronoteModeCounts[option.value] ?? 1));
      return acc;
    }, {});
    if (selectedPronoteModes.includes("matching")) {
      pronoteModeJson["matching_pairs_per_question"] = matchingPairsPerQuestion;
    }
    const sections = [
      instructions.trim(),
      learningGoal.trim() ? `Objectif: ${learningGoal.trim()}` : "",
      pronoteDistribution ? `Distribution pronote demandee (nb d'items):\n${pronoteDistribution}` : "",
      pronoteHints ? `Contraintes pronote par type:\n${pronoteHints}` : "",
      activePronoteOptions.length > 0 ? `PRONOTE_MODES_JSON: ${JSON.stringify(pronoteModeJson)}` : "",
      "Style attendu: ne numerotez jamais les enonces (pas de Q1, Question 1, Item 1). Gardez uniquement la question."
    ].filter(Boolean);

    const nonPronoteCount = pronoteOnly ? 0 : nonPronoteRequestedCount;
    const desired = pronoteRequestedCount + nonPronoteCount;

    return {
      contentTypes,
      maxItems: Math.min(100, Math.max(1, desired || generationCount)),
      instructions: sections.length > 0 ? sections.join("\n\n") : undefined
    };
  }

  useEffect(() => {
    if (step !== 4 || items.length === 0) return;
    const normalized = normalizeItemsForEditor(items);
    if (itemsNeedNormalization(items, normalized)) {
      setItems(normalized);
    }
  }, [items, step]);

  useEffect(() => {
    if (step !== 1 && showPronoteImportPanel) {
      setShowPronoteImportPanel(false);
    }
  }, [showPronoteImportPanel, step]);

  async function runGenerate(plan: { contentTypes: ContentType[]; maxItems: number; instructions?: string }) {
    setBusy(true);
    setBusyPhase("generate");
    setError("");
    setJobProgress(0);
    try {
      const { authToken, project } = await ensureAuthAndProject();
      const reviewedText = sourceReviewText.trim();
      if (reviewedText.length > 0) {
        await updateSourceDocument(authToken, project, { plain_text: reviewedText });
      }

      const generated = await launchGenerate(authToken, project, {
        content_types: plan.contentTypes,
        instructions: plan.instructions,
        max_items: plan.maxItems,
        language: "fr",
        level: classLevel || "intermediate",
        subject: subject.trim() || undefined,
        class_level: classLevel.trim() || undefined,
        difficulty_target: difficultyTarget.trim() || undefined
      });
      const job = await pollJobUntilDone(authToken, generated.job_id, (next) => setJobProgress(next.progress));
      setJobProgress(job.progress);

      const content = await getContent(authToken, project);
      setContentSetId(content.content_set_id);
      setItems(normalizeItemsForEditor(content.items));
      await refreshQualityPreview(authToken, project);
      await refreshAnalytics(authToken, project);
      setStep(4);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur generation");
    } finally {
      setBusy(false);
      setBusyPhase(null);
    }
  }

  async function handleGenerate() {
    const plan = buildGenerationPlan();
    if (plan.contentTypes.length === 0) {
      setError("Selectionnez au moins un type de contenu a generer.");
      return;
    }
    await runGenerate(plan);
  }

  async function handleQuickPronoteGenerate() {
    const plan = buildGenerationPlan({ pronoteOnly: true });
    if (plan.contentTypes.length === 0) {
      setError("Selectionnez au moins un type d'exercice Pronote.");
      return;
    }
    await runGenerate(plan);
  }

  function updateItem(index: number, patch: Partial<ContentItem>) {
    const normalizedPatch: Partial<ContentItem> = { ...patch };
    if (typeof normalizedPatch.prompt === "string") {
      normalizedPatch.prompt = stripQuestionPrefix(normalizedPatch.prompt);
    }
    if (typeof normalizedPatch.correct_answer === "string") {
      normalizedPatch.correct_answer = normalizeAnswerText(normalizedPatch.correct_answer);
    }
    if (Array.isArray(normalizedPatch.distractors)) {
      normalizedPatch.distractors = normalizedPatch.distractors.map((entry) => stripTrailingCounter(entry));
    }
    setItems((current) =>
      current.map((item, idx) => {
        if (idx !== index) return item;
        const nextItem: ContentItem = { ...item, ...normalizedPatch };
        if (nextItem.item_type === "cloze") {
          const clozePatch = buildClozePatch(nextItem, buildClozeExpectedAnswers(nextItem));
          nextItem.correct_answer = clozePatch.correct_answer;
        }
        return nextItem;
      })
    );
  }

  function addItem() {
    setItems((current) => [
      ...current,
      {
        id: `tmp-${Date.now()}`,
        item_type: "mcq",
        prompt: "Nouvelle question",
        correct_answer: "",
        distractors: ["", "", ""],
        answer_options: [],
        tags: [],
        difficulty: "medium",
        feedback: "",
        source_reference: "section:1",
        position: current.length
      }
    ]);
  }

  function removeItem(index: number) {
    setItems((current) => current.filter((_, idx) => idx !== index).map((item, idx) => ({ ...item, position: idx })));
  }

  async function handleSaveContent() {
    setBusy(true);
    setBusyPhase("save");
    setError("");
    try {
      const { authToken, project } = await ensureAuthAndProject();
      const normalizedItems = normalizeItemsForEditor(items).map((item) => {
        if (item.item_type !== "cloze") return item;
        const clozePatch = buildClozePatch(item, buildClozeExpectedAnswers(item));
        return { ...item, correct_answer: clozePatch.correct_answer };
      });
      setItems(normalizedItems);
      const saved = await saveContent(authToken, project, {
        content_set_id: contentSetId,
        items: normalizedItems
      });
      setItems(normalizeItemsForEditor(saved.items));
      await refreshQualityPreview(authToken, project);
      await refreshAnalytics(authToken, project);
      setStep(5);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur sauvegarde");
    } finally {
      setBusy(false);
      setBusyPhase(null);
    }
  }

  async function handleExport() {
    setBusy(true);
    setBusyPhase("export");
    setError("");
    setDownloadUrl("");
    setJobProgress(0);
    try {
      const { authToken, project } = await ensureAuthAndProject();
      const launch = await launchExport(authToken, project, {
        format: exportFormat,
        options:
          exportFormat === "pronote_xml"
            ? {
                answernumbering: "123",
                niveau: classLevel.trim() || "",
                matiere: subject.trim() || "",
                shuffle_answers: pronoteShuffleAnswers,
              }
            : {}
      });
      const job = await pollJobUntilDone(authToken, launch.job_id, (next) => setJobProgress(next.progress));
      if (!job.result_id) {
        throw new Error("Export termine sans identifiant d'artefact");
      }
      const downloadable = await getExportDownload(authToken, job.result_id);
      setDownloadUrl(downloadable.url);
      triggerBrowserDownload(downloadable.url);
      await refreshAnalytics(authToken, project);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur export");
    } finally {
      setBusy(false);
      setBusyPhase(null);
    }
  }

  async function handleSaveAndDownloadPronote() {
    setBusy(true);
    setBusyPhase("export");
    setError("");
    setDownloadUrl("");
    setJobProgress(0);
    setExportFormat("pronote_xml");

    try {
      const { authToken, project } = await ensureAuthAndProject();
      const normalizedItems = normalizeItemsForEditor(items).map((item) => {
        if (item.item_type !== "cloze") return item;
        const clozePatch = buildClozePatch(item, buildClozeExpectedAnswers(item));
        return { ...item, correct_answer: clozePatch.correct_answer };
      });
      setItems(normalizedItems);
      const saved = await saveContent(authToken, project, {
        content_set_id: contentSetId,
        items: normalizedItems
      });
      setItems(normalizeItemsForEditor(saved.items));
      await refreshQualityPreview(authToken, project);

      const launch = await launchExport(authToken, project, {
        format: "pronote_xml",
        options: {
          answernumbering: "123",
          niveau: classLevel.trim() || "",
          matiere: subject.trim() || "",
          shuffle_answers: pronoteShuffleAnswers,
        }
      });
      const job = await pollJobUntilDone(authToken, launch.job_id, (next) => setJobProgress(next.progress));
      if (!job.result_id) {
        throw new Error("Export termine sans identifiant d'artefact");
      }
      const downloadable = await getExportDownload(authToken, job.result_id);
      setDownloadUrl(downloadable.url);
      triggerBrowserDownload(downloadable.url);
      await refreshAnalytics(authToken, project);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur export PRONOTE");
    } finally {
      setBusy(false);
      setBusyPhase(null);
    }
  }

  function triggerBrowserDownload(url: string) {
    const link = document.createElement("a");
    link.href = url;
    link.setAttribute("download", "");
    link.style.display = "none";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  async function handleImportPronoteXml() {
    if (!pronoteImportXml.trim()) {
      setError("Collez le XML Pronote avant import.");
      return;
    }
    setBusy(true);
    setBusyPhase("save");
    setError("");
    try {
      const { authToken, project } = await ensureAuthAndProject();
      const imported = await importPronoteXml(authToken, project, {
        xml_content: pronoteImportXml.trim(),
        source_filename: pronoteImportFilename.trim() || undefined,
        replace_current_content: replaceContentOnImport
      });
      setImportResult(imported);
      const content = await getContent(authToken, project);
      setContentSetId(content.content_set_id);
      setItems(normalizeImportedItems ? normalizeItemsForEditor(content.items) : content.items);
      await refreshQualityPreview(authToken, project);
      await refreshAnalytics(authToken, project);
      setShowPronoteImportPanel(false);
      setStep(openEditorAfterImport ? 4 : 3);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erreur import Pronote");
    } finally {
      setBusy(false);
      setBusyPhase(null);
    }
  }

  function labelDifficulty(value: string): string {
    if (value === "easy" || value === "facile") return "facile";
    if (value === "hard" || value === "avance") return "avance";
    return "intermediaire";
  }

  function normalizeDifficultyValue(value: string): "easy" | "medium" | "hard" {
    const normalized = value.trim().toLowerCase();
    if (normalized === "easy" || normalized === "facile") return "easy";
    if (normalized === "hard" || normalized === "avance") return "hard";
    return "medium";
  }

  function labelItemType(item: ContentItem): string {
    const type = item.item_type;
    const prompt = item.prompt.toLowerCase();
    const tags = item.tags.map((tag) => tag.toLowerCase());
    const answer = (item.correct_answer ?? "").trim();

    if (type === "mcq") {
      const looksMultiple =
        prompt.includes("plusieurs reponses") ||
        prompt.includes("choix multiple") ||
        tags.includes("multiple_choice");
      return looksMultiple ? "Choix multiple" : "Choix unique";
    }
    if (type === "poll") return "Choix multiple";
    if (type === "matching") return "Association";
    if (type === "cloze") {
      if (tags.includes("cloze_list_variable")) return "Texte a trous (liste variable)";
      if (tags.includes("cloze_list_unique")) return "Texte a trous (liste unique)";
      return "Texte a trous";
    }
    if (type === "open_question") {
      if (prompt.includes("epelle") || tags.includes("spelling")) return "Epellation";
      if (/^-?\d+(?:[.,]\d+)?(?:\s*[%a-zA-Z°]+)?$/.test(answer)) return "Valeur numerique";
      return "Reponse a saisir";
    }
    if (type === "brainstorming") return "Brainstorming";
    if (type === "flashcard") return "Flashcard";
    if (type === "course_structure") return "Structure de cours";
    return type;
  }

  function splitExpectedAnswers(value: string | undefined): string[] {
    if (!value) return [];
    const chunks = value.split(/\|\||;;|;|\n/);
    const seen = new Set<string>();
    const answers: string[] = [];
    for (const chunk of chunks) {
      const normalized = chunk.trim();
      if (!normalized) continue;
      const key = normalized.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      answers.push(normalized);
    }
    return answers;
  }

  function splitExpectedAnswersKeepDuplicates(value: string | undefined): string[] {
    if (!value) return [];
    return value
      .split(/\|\||;;|;|\n/)
      .map((chunk) => chunk.trim())
      .filter((chunk) => chunk.length > 0);
  }

  function countClozeHoles(prompt: string): number {
    if (!prompt.trim()) return 0;
    const matches = prompt.match(CLOZE_HOLE_PATTERN);
    return matches ? matches.length : 0;
  }

  function dedupeChoiceValues(values: string[]): string[] {
    const seen = new Set<string>();
    const deduped: string[] = [];
    for (const raw of values) {
      const normalized = raw.trim();
      if (!normalized) continue;
      const key = normalized.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      deduped.push(normalized);
    }
    return deduped;
  }

  function splitEditorList(rawValue: string): string[] {
    const parts = rawValue.split(/;|\n|\|\|/);
    return dedupeChoiceValues(parts);
  }

  function buildClozeExpectedAnswers(item: ContentItem): string[] {
    const expected = splitExpectedAnswersKeepDuplicates(item.correct_answer);
    const holeCount = Math.max(1, countClozeHoles(item.prompt));
    const fallbackWords = dedupeChoiceValues([...item.answer_options, ...item.distractors]);
    const next = [...expected];

    for (const fallback of fallbackWords) {
      if (next.length >= holeCount) break;
      if (next.some((value) => value.toLowerCase() === fallback.toLowerCase())) continue;
      next.push(fallback);
    }

    while (next.length < holeCount) {
      next.push(`mot${next.length + 1}`);
    }

    return next.slice(0, holeCount);
  }

  function buildClozePatch(item: ContentItem, answers: string[]): Partial<ContentItem> {
    const requiredCount = Math.max(1, countClozeHoles(item.prompt));
    const cleanedAnswers = answers.map((value) => value.trim()).filter((value) => value.length > 0);

    while (cleanedAnswers.length < requiredCount) {
      cleanedAnswers.push(`mot${cleanedAnswers.length + 1}`);
    }

    return {
      correct_answer: cleanedAnswers.slice(0, requiredCount).join(" || ")
    };
  }

  function handleClozeAnswerChange(
    index: number,
    item: ContentItem,
    answerIndex: number,
    nextValue: string
  ): void {
    const answers = buildClozeExpectedAnswers(item);
    answers[answerIndex] = nextValue;
    updateItem(index, buildClozePatch(item, answers));
  }

  function isWeakMatchingText(value: string): boolean {
    const normalized = value.trim().toLowerCase();
    if (!normalized) return true;
    if (/^(definition|def|desc)\s+de\b/.test(normalized)) return true;
    if (/^(element|notion|terme)\s+[a-z0-9]+$/.test(normalized)) return true;
    return false;
  }

  function isWeakMatchingConcept(value: string): boolean {
    const normalized = value.trim().toLowerCase();
    if (!normalized) return true;
    if (/^(on|il|elle|ils|elles|nous|vous|ce|cet|cette|cela|ceci|bien|toutes?|chaque)\b/.test(normalized)) {
      return true;
    }
    if (/\b(est|sont|sera|seront|doit|doivent|peut|peuvent|faut|suppose|considere|arrive|arrivent|perd|perdent)\b/.test(normalized)) {
      return true;
    }
    return false;
  }

  function normalizeMatchingDefinition(left: string, right: string): string {
    const cleaned = right.trim();
    if (!cleaned) return cleaned;
    if (/^(?:(?:c['’]?\s*est|est)\s*[-–]?\s*a\s*[-–]?\s*dire)\b/i.test(cleaned)) {
      const tail = cleaned
        .replace(/^(?:(?:c['’]?\s*est|est)\s*[-–]?\s*a\s*[-–]?\s*dire)\b[:\s,-]*/i, "")
        .trim();
      return tail ? `Se definit ainsi: ${tail}` : cleaned;
    }
    if (/^(est|sont|correspond(?:ent)?\s+a|permet(?:tent)?\s+de|sert(?:vent)?\s+a|consiste(?:nt)?\s+a|represente(?:nt)?)\b/i.test(cleaned)) {
      return `${left.trim()} ${cleaned}`.trim();
    }
    return cleaned;
  }

  function parseMatchingPairsFromItem(item: ContentItem): MatchingPair[] {
    const seen = new Set<string>();
    const pairs: MatchingPair[] = [];
    const rawCandidates = [item.correct_answer ?? "", ...item.answer_options];

    for (const candidate of rawCandidates) {
      const parts = candidate
        .split(/;|\n/)
        .map((part) => part.trim())
        .filter((part) => part.length > 0);
      for (const part of parts) {
        let left = "";
        let right = "";
        // Try arrow separators first (safe), then " = " with spaces (avoid splitting words)
        for (const separator of ["->", "=>"]) {
          if (part.includes(separator)) {
            const split = part.split(separator);
            left = (split[0] ?? "").trim();
            right = split.slice(1).join(separator).trim();
            break;
          }
        }
        // " = " with spaces only (avoid cutting words containing =)
        if (!left && part.includes(" = ")) {
          const split = part.split(" = ");
          left = (split[0] ?? "").trim();
          right = split.slice(1).join(" = ").trim();
        }
        if (!left && part.includes(":")) {
          const split = part.split(":");
          left = (split[0] ?? "").trim();
          right = split.slice(1).join(":").trim();
        }
        if (!left || !right) continue;
        right = normalizeMatchingDefinition(left, right);
        // Relaxed validation: allow 1-word concepts and 2-word definitions
        if (left.split(/\s+/).length > 12) continue;
        if (right.split(/\s+/).length < 2) continue;
        if (right.split(/\s+/).length > 40) continue;
        if (isWeakMatchingText(left) || isWeakMatchingText(right)) continue;
        // Deduplicate: exact match AND near-duplicate by left concept
        const key = `${left.toLowerCase()}::${right.toLowerCase()}`;
        if (seen.has(key)) continue;
        const leftNorm = left.toLowerCase().replace(/[^a-zà-ÿ0-9]/g, "");
        const isDuplicateLeft = [...seen].some((k) => {
          const existingLeft = k.split("::")[0]?.replace(/[^a-zà-ÿ0-9]/g, "") ?? "";
          return existingLeft === leftNorm;
        });
        if (isDuplicateLeft) continue;
        seen.add(key);
        pairs.push({ left, right });
      }
    }

    if (pairs.length >= 2) return pairs;

    return [
      {
        left: "Notion reseau 1",
        right: "Description complete de la notion, redigee comme une phrase claire."
      },
      {
        left: "Notion reseau 2",
        right: "Deuxieme description detaillee qui reste coherente avec le texte source."
      }
    ];
  }

  function buildMatchingPatch(item: ContentItem, pairs: MatchingPair[]): Partial<ContentItem> {
    const cleaned = pairs
      .map((pair) => ({
        left: pair.left.trim(),
        right: pair.right.trim()
      }))
      .filter((pair) => pair.left.length > 0 && pair.right.length > 0);

    const serialized = cleaned.map((pair) => `${pair.left} -> ${pair.right}`);
    return {
      correct_answer: serialized.join(" ; "),
      answer_options: serialized,
      distractors: [],
      tags: item.tags
    };
  }

  function handleMatchingPairChange(
    index: number,
    item: ContentItem,
    pairIndex: number,
    side: "left" | "right",
    value: string
  ): void {
    const pairs = parseMatchingPairsFromItem(item);
    const nextPairs = [...pairs];
    const current = nextPairs[pairIndex] ?? { left: "", right: "" };
    nextPairs[pairIndex] = side === "left" ? { ...current, left: value } : { ...current, right: value };
    updateItem(index, buildMatchingPatch(item, nextPairs));
  }

  function handleMatchingAdd(index: number, item: ContentItem): void {
    const pairs = parseMatchingPairsFromItem(item);
    const nextPairs = [
      ...pairs,
      {
        left: `Notion ${pairs.length + 1}`,
        right: "Nouvelle description complete a associer."
      }
    ];
    updateItem(index, buildMatchingPatch(item, nextPairs));
  }

  function handleMatchingRemove(index: number, item: ContentItem, pairIndex: number): void {
    const pairs = parseMatchingPairsFromItem(item);
    const nextPairs = pairs.filter((_, idx) => idx !== pairIndex);
    updateItem(index, buildMatchingPatch(item, nextPairs));
  }

  function isChoiceQuestion(item: ContentItem): boolean {
    return item.item_type === "mcq" || item.item_type === "poll";
  }

  function allowsMultipleCorrectAnswers(item: ContentItem): boolean {
    if (item.item_type === "poll") return true;
    const prompt = item.prompt.toLowerCase();
    const tags = item.tags.map((tag) => tag.toLowerCase());
    return (
      prompt.includes("plusieurs reponses") ||
      prompt.includes("choix multiple") ||
      tags.includes("multiple_choice")
    );
  }

  function buildChoiceEditorState(item: ContentItem): { choices: string[]; correctKeys: Set<string> } {
    const expected = splitExpectedAnswers(item.correct_answer);
    const choices = dedupeChoiceValues([...expected, ...item.answer_options, ...item.distractors]);
    const correctKeys = new Set(expected.map((answer) => answer.toLowerCase()));
    if (choices.length === 0) {
      choices.push("Nouvelle reponse");
    }
    if (correctKeys.size === 0 && choices[0]) {
      correctKeys.add(choices[0].toLowerCase());
    }
    return { choices, correctKeys };
  }

  function buildChoicePatch(
    item: ContentItem,
    choices: string[],
    correctKeys: Set<string>,
    allowMultiple: boolean
  ): Partial<ContentItem> {
    const cleanedChoices = dedupeChoiceValues(choices);
    let expectedAnswers = cleanedChoices.filter((choice) => correctKeys.has(choice.toLowerCase()));
    if (!allowMultiple && expectedAnswers.length > 1) {
      expectedAnswers = [expectedAnswers[0]];
    }
    if (cleanedChoices.length > 0 && expectedAnswers.length === 0) {
      expectedAnswers = [cleanedChoices[0]];
    }
    const expectedSet = new Set(expectedAnswers.map((choice) => choice.toLowerCase()));
    const distractors = cleanedChoices.filter((choice) => !expectedSet.has(choice.toLowerCase()));
    return {
      correct_answer: expectedAnswers.join(" || "),
      distractors,
      answer_options: cleanedChoices,
      tags: item.tags
    };
  }

  function handleChoiceToggle(index: number, item: ContentItem, choiceIndex: number, checked: boolean): void {
    const allowMultiple = allowsMultipleCorrectAnswers(item);
    const state = buildChoiceEditorState(item);
    const choice = state.choices[choiceIndex];
    if (!choice) return;
    const key = choice.toLowerCase();
    const nextCorrect = new Set(state.correctKeys);
    if (checked) {
      if (!allowMultiple) {
        nextCorrect.clear();
      }
      nextCorrect.add(key);
    } else {
      nextCorrect.delete(key);
    }
    updateItem(index, buildChoicePatch(item, state.choices, nextCorrect, allowMultiple));
  }

  function handleChoiceTextChange(index: number, item: ContentItem, choiceIndex: number, nextValue: string): void {
    const allowMultiple = allowsMultipleCorrectAnswers(item);
    const state = buildChoiceEditorState(item);
    const nextChoices = [...state.choices];
    const previous = nextChoices[choiceIndex] ?? "";
    nextChoices[choiceIndex] = nextValue;
    const nextCorrect = new Set(state.correctKeys);
    const previousKey = previous.trim().toLowerCase();
    const nextKey = nextValue.trim().toLowerCase();
    if (previousKey && nextCorrect.has(previousKey)) {
      nextCorrect.delete(previousKey);
      if (nextKey) {
        nextCorrect.add(nextKey);
      }
    }
    updateItem(index, buildChoicePatch(item, nextChoices, nextCorrect, allowMultiple));
  }

  function handleChoiceAdd(index: number, item: ContentItem): void {
    const allowMultiple = allowsMultipleCorrectAnswers(item);
    const state = buildChoiceEditorState(item);
    const nextChoices = [...state.choices, `Nouvelle reponse ${state.choices.length + 1}`];
    updateItem(index, buildChoicePatch(item, nextChoices, state.correctKeys, allowMultiple));
  }

  function handleChoiceRemove(index: number, item: ContentItem, choiceIndex: number): void {
    const allowMultiple = allowsMultipleCorrectAnswers(item);
    const state = buildChoiceEditorState(item);
    const choice = state.choices[choiceIndex] ?? "";
    const nextChoices = state.choices.filter((_, idx) => idx !== choiceIndex);
    const nextCorrect = new Set(state.correctKeys);
    nextCorrect.delete(choice.trim().toLowerCase());
    updateItem(index, buildChoicePatch(item, nextChoices, nextCorrect, allowMultiple));
  }

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
          <span className="teacher-badge">Espace enseignant</span>
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
                                      togglePronoteMode(mode);
                                    }}
                                  >
                                    <span className="pronote-choice-title">
                                      {checked ? "✓ " : ""}
                                      {option.title}
                                    </span>
                                    <span className="pronote-choice-subtitle">{option.subtitle}</span>
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        ))}
                      </div>

                      <div className="pronote-counts-panel mt-3">
                        <p className="pronote-counts-title">Nombre de questions par type sélectionné</p>
                        {selectedPronoteOptions.length === 0 ? (
                          <p className="text-sm text-slate-600">Selectionnez au moins un type d&apos;exercice.</p>
                        ) : (
                          <div className="pronote-counts-grid">
                            {selectedPronoteOptions.map((option) =>
                              option.value === "matching" ? (
                                <div key={option.value} className="pronote-matching-row">
                                  <label className="pronote-matching-count-label">
                                    <span className="pronote-matching-icon">🔗</span>
                                    {option.title}
                                    <input
                                      className="pronote-mode-count"
                                      type="number"
                                      min={1}
                                      max={100}
                                      value={pronoteModeCounts[option.value] ?? 1}
                                      onClick={(event) => event.stopPropagation()}
                                      onChange={(event) => updatePronoteModeCount(option.value, event.target.value)}
                                    />
                                  </label>
                                  <div className="pronote-matching-divider" />
                                  <label className="pronote-matching-pairs-label">
                                    Paires / question
                                    <input
                                      className="pronote-mode-count"
                                      type="number"
                                      min={2}
                                      max={6}
                                      value={matchingPairsPerQuestion}
                                      onClick={(event) => event.stopPropagation()}
                                      onChange={(event) => {
                                        const v = parseInt(event.target.value, 10);
                                        setMatchingPairsPerQuestion(Number.isNaN(v) ? 3 : Math.min(6, Math.max(2, v)));
                                      }}
                                    />
                                  </label>
                                </div>
                              ) : (
                                <label key={option.value} className="text-sm font-medium text-slate-800">
                                  {option.title}
                                  <input
                                    className="pronote-mode-count"
                                    type="number"
                                    min={1}
                                    max={100}
                                    value={pronoteModeCounts[option.value] ?? 1}
                                    onClick={(event) => event.stopPropagation()}
                                    onChange={(event) => updatePronoteModeCount(option.value, event.target.value)}
                                  />
                                </label>
                              )
                            )}
                          </div>
                        )}
                        <p className="pronote-total">Total questions Pronote: {pronoteRequestedCount} / 100</p>
                      </div>

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
                            disabled={busy || selectedPronoteModes.length === 0}
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

          <div className="elea-space mt-4">
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
            <button type="button" className="primary" onClick={handleGenerate} disabled={selectedContentTypes.length === 0 || busy}>
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
