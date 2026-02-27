import { type Dispatch, type SetStateAction } from "react";
import { ContentItem } from "@/lib/types";
import {
    CLOZE_HOLE_PATTERN,
    MatchingPair,
    stripQuestionPrefix,
    normalizeAnswerText,
    stripTrailingCounter,
} from "@/lib/utils";

// ── Pure helpers (stateless) ──────────────────────────────

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
    if (/^(?:(?:c[''']?\s*est|est)\s*[-–]?\s*a\s*[-–]?\s*dire)\b/i.test(cleaned)) {
        const tail = cleaned
            .replace(/^(?:(?:c[''']?\s*est|est)\s*[-–]?\s*a\s*[-–]?\s*dire)\b[:\s,-]*/i, "")
            .trim();
        return tail ? `Se definit ainsi: ${tail}` : cleaned;
    }
    if (/^(est|sont|correspond(?:ent)?\s+a|permet(?:tent)?\s+de|sert(?:vent)?\s+a|consiste(?:nt)?\s+a|represente(?:nt)?)\b/i.test(cleaned)) {
        return `${left.trim()} ${cleaned}`.trim();
    }
    return cleaned;
}

// ── Exported pure helpers ──────────────────────────────────

export function parseMatchingPairsFromItem(item: ContentItem): MatchingPair[] {
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
            for (const separator of ["->", "=>"]) {
                if (part.includes(separator)) {
                    const split = part.split(separator);
                    left = (split[0] ?? "").trim();
                    right = split.slice(1).join(separator).trim();
                    break;
                }
            }
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
            if (left.split(/\s+/).length > 12) continue;
            if (right.split(/\s+/).length < 2) continue;
            if (right.split(/\s+/).length > 40) continue;
            if (isWeakMatchingText(left) || isWeakMatchingText(right)) continue;
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

export function buildClozeExpectedAnswers(item: ContentItem): string[] {
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

export function buildClozePatch(item: ContentItem, answers: string[]): Partial<ContentItem> {
    const requiredCount = Math.max(1, countClozeHoles(item.prompt));
    const cleanedAnswers = answers.map((value) => value.trim()).filter((value) => value.length > 0);

    while (cleanedAnswers.length < requiredCount) {
        cleanedAnswers.push(`mot${cleanedAnswers.length + 1}`);
    }

    return {
        correct_answer: cleanedAnswers.slice(0, requiredCount).join(" || ")
    };
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

// ── Hook ──────────────────────────────────────────────────

export function useItemEditor(
    items: ContentItem[],
    setItems: Dispatch<SetStateAction<ContentItem[]>>
) {
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

    return {
        updateItem,
        addItem,
        removeItem,
        // Cloze
        handleClozeAnswerChange,
        buildClozeExpectedAnswers,
        countClozeHoles,
        // Matching
        handleMatchingPairChange,
        handleMatchingAdd,
        handleMatchingRemove,
        parseMatchingPairsFromItem,
        // Choice (MCQ / Poll)
        handleChoiceToggle,
        handleChoiceTextChange,
        handleChoiceAdd,
        handleChoiceRemove,
        isChoiceQuestion,
        allowsMultipleCorrectAnswers,
        buildChoiceEditorState,
        // Util re-exports
        dedupeChoiceValues,
        splitExpectedAnswers,
        splitEditorList: (rawValue: string): string[] => {
            const parts = rawValue.split(/;|\n|\|\|/);
            return dedupeChoiceValues(parts);
        }
    };
}
