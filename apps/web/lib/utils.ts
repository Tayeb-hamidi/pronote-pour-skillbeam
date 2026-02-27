import { ContentItem, ContentType, ExportFormat, SourceType } from "./types";

// ── Types ──────────────────────────────────────────────────
export type BusyPhase = "ingest" | "generate" | "save" | "export" | null;

export type PronoteExerciseMode =
    | "single_choice"
    | "multiple_choice"
    | "numeric_value"
    | "free_response"
    | "spelling"
    | "cloze_free"
    | "cloze_list_unique"
    | "cloze_list_variable"
    | "matching";

export interface MatchingPair {
    left: string;
    right: string;
}

export interface PronoteExerciseOption {
    value: PronoteExerciseMode;
    title: string;
    subtitle: string;
    contentType: ContentType;
    generationHint: string;
}

export interface PronoteExerciseFamily {
    title: string;
    subtitle: string;
    modes: PronoteExerciseMode[];
}

// ── Constants ──────────────────────────────────────────────
export const STEP_LABELS = ["Source", "Ingestion", "Generation", "Edition", "Export"];
export const MAX_UPLOAD_BYTES = 200 * 1024 * 1024;

export const CLASS_LEVEL_OPTIONS = [
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

export const SOURCE_OPTIONS: Array<{
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

export const CONTENT_OPTIONS: Array<{ value: ContentType; title: string; subtitle: string }> = [
    { value: "mcq", title: "QCM Pronote", subtitle: "Bonne reponse + distracteurs" },
    { value: "course_structure", title: "Structure cours", subtitle: "TOC, glossaire, concepts, resumes" },
    { value: "poll", title: "Sondage", subtitle: "Choix multiples sans bonne reponse" },
    { value: "open_question", title: "Questions ouvertes", subtitle: "Attendus de correction" },
    { value: "cloze", title: "Textes a trous", subtitle: "Completions ciblees" },
    { value: "brainstorming", title: "Brainstorming", subtitle: "Categories + idees" },
    { value: "flashcards", title: "Flashcards", subtitle: "Recto/verso revision" }
];

export const PRONOTE_EXERCISE_OPTIONS: PronoteExerciseOption[] = [
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

export const PRONOTE_EXERCISE_FAMILIES: PronoteExerciseFamily[] = [
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

export const EXPORT_OPTIONS: Array<{ value: ExportFormat; title: string; subtitle: string }> = [
    { value: "docx", title: "Word (DOCX)", subtitle: "Document modifiable" },
    { value: "pdf", title: "PDF", subtitle: "Mise en page rapide" },
    { value: "xlsx", title: "Excel (XLSX)", subtitle: "Table de questions" },
    { value: "moodle_xml", title: "Moodle XML", subtitle: "Import quiz Moodle" },
    { value: "pronote_xml", title: "PRONOTE XML", subtitle: "Format XML strict pronote" },
    { value: "qti", title: "QTI", subtitle: "Placeholder structure IMS" },
    { value: "h5p", title: "H5P", subtitle: "QuestionSet best-effort" },
    { value: "anki", title: "Anki", subtitle: "CSV compatible revision" }
];

export const THEME_PRESET_TOPICS = [
    "Renaissance et humanisme",
    "Révolution industrielle",
    "Énergie et transition écologique",
    "Citoyenneté numérique",
    "Probabilités et statistiques",
    "Argumentation en français"
];

export const DIFFICULTY_OPTIONS: Array<{ value: string; label: string; hint: string }> = [
    { value: "easy", label: "Facile", hint: "Notions de base, questions directes." },
    { value: "medium", label: "Intermédiaire", hint: "Compréhension + application." },
    { value: "hard", label: "Avancé", hint: "Analyse, justification, mise en relation." }
];

export const CLOZE_HOLE_PATTERN =
    /(?:_{2,}|\{\{\s*blank\s*\}\}|\[\s*blank\s*\]|\(\s*blank\s*\)|\{:MULTICHOICE:[^}]+\})/gi;

// ── Pure utility functions ─────────────────────────────────
export function stripQuestionPrefix(value: string): string {
    let next = value.trim();
    const patterns = [
        /^\s*item\s*#?\s*\d{1,3}\s*(?:[:.)\-]\s*)/i,
        /^\s*q\s*#?\s*\d{1,3}\s*(?:[:.)\-]\s*|\s+)/i,
        /^\s*question\s*(?:ouverte|open|qcm|a\s*saisir|numerique|texte\s*a\s*trous|association|choix\s*multiple|choix\s*unique)?\s*#?\s*\d{1,3}\s*(?:[:.)\-]\s*|\s+)/i,
        /^\s*\d{1,3}\s*[:.)\-]\s*/i
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

export function stripTrailingCounter(value: string): string {
    return value.replace(/\s*[[(]\s*\d{1,3}\s*[\])]\s*$/g, "").trim();
}

export function normalizeAnswerText(value: string | undefined): string | undefined {
    if (!value) return value;
    const cleaned = stripTrailingCounter(value.replace(/^reponse\s*[:\-]\s*/i, "").trim());
    return cleaned;
}

export function normalizeItemsForEditor(sourceItems: ContentItem[]): ContentItem[] {
    return sourceItems.map((item, index) => ({
        ...item,
        prompt: stripQuestionPrefix(item.prompt),
        correct_answer: normalizeAnswerText(item.correct_answer),
        distractors: item.distractors.map((entry) => stripTrailingCounter(entry)),
        position: Number.isFinite(item.position) ? item.position : index
    }));
}

export function itemsNeedNormalization(sourceItems: ContentItem[], normalizedItems: ContentItem[]): boolean {
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

export function summarizePronoteXml(xml: string): {
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

export function formatFileSize(sizeBytes: number): string {
    if (sizeBytes < 1024) return `${sizeBytes} o`;
    if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} Ko`;
    return `${(sizeBytes / (1024 * 1024)).toFixed(1)} Mo`;
}

export function labelDifficulty(value: string): string {
    const option = DIFFICULTY_OPTIONS.find((opt) => opt.value === value);
    return option?.label ?? value;
}

export function normalizeDifficultyValue(value: string): "easy" | "medium" | "hard" {
    const lower = value.toLowerCase().trim();
    if (lower === "facile" || lower === "easy") return "easy";
    if (lower === "avancé" || lower === "difficile" || lower === "hard") return "hard";
    return "medium";
}

export function labelItemType(item: ContentItem): string {
    switch (item.item_type) {
        case "mcq":
            return "QCM";
        case "open_question":
            return "Question ouverte";
        case "flashcards":
            return "Flashcard";
        case "poll":
            return "Sondage";
        case "cloze":
            return "Texte à trous";
        case "matching":
            return "Association";
        case "course_structure":
            return "Structure";
        case "brainstorming":
            return "Brainstorming";
        default:
            return item.item_type ?? "Inconnu";
    }
}
