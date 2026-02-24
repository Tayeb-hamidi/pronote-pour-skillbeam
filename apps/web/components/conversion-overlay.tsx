"use client";

import { useEffect, useState } from "react";
import { ExportFormat } from "@/lib/types";

const FORMAT_LABELS: Record<ExportFormat, string> = {
  docx: "DOCX",
  pdf: "PDF",
  xlsx: "XLSX",
  moodle_xml: "Moodle XML",
  pronote_xml: "PRONOTE XML",
  qti: "QTI",
  h5p: "H5P",
  anki: "Anki"
};

const PEDAGOGICAL_QUOTES = [
  {
    text: "L'homme ne peut devenir homme que par l'education.",
    author: "Immanuel Kant"
  },
  {
    text: "Mieux vaut une tete bien faite qu'une tete bien pleine.",
    author: "Montaigne"
  },
  {
    text: "L'education n'est pas une preparation a la vie ; l'education est la vie meme.",
    author: "John Dewey"
  },
  {
    text: "Vivre est le metier que je veux lui apprendre.",
    author: "Jean-Jacques Rousseau"
  },
  {
    text: "L'education est le point ou se decide si nous aimons assez le monde pour en assumer la responsabilite.",
    author: "Hannah Arendt"
  },
  {
    text: "Personne n'eduque autrui, personne ne s'eduque seul : les hommes s'eduquent ensemble.",
    author: "Paulo Freire"
  },
  {
    text: "Connais-toi toi-meme.",
    author: "Socrate"
  },
  {
    text: "Une vie sans examen ne vaut pas la peine d'etre vecue.",
    author: "Socrate"
  },
  {
    text: "Je sais que je ne sais rien.",
    author: "Socrate"
  },
  {
    text: "L'esprit n'est pas un vase a remplir, mais un feu a allumer.",
    author: "Plutarque"
  },
  {
    text: "L'education a des racines ameres, mais ses fruits sont doux.",
    author: "Aristote"
  },
  {
    text: "Le commencement est la moitie du tout.",
    author: "Aristote"
  },
  {
    text: "Le bonheur depend de nous.",
    author: "Aristote"
  },
  {
    text: "Rien n'est permanent, sauf le changement.",
    author: "Heraclite"
  },
  {
    text: "Le caractere d'un homme est son destin.",
    author: "Heraclite"
  },
  {
    text: "Ce qui trouble les hommes, ce ne sont pas les choses, mais l'idee qu'ils s'en font.",
    author: "Epictete"
  },
  {
    text: "N'attends pas que les evenements arrivent comme tu le souhaites ; decide de vouloir ce qui arrive.",
    author: "Epictete"
  },
  {
    text: "La qualite de ta vie depend de la qualite de tes pensees.",
    author: "Marc Aurele"
  },
  {
    text: "Que chaque action ait sa raison et sa mesure.",
    author: "Marc Aurele"
  },
  {
    text: "Ce n'est pas parce que les choses sont difficiles que nous n'osons pas ; c'est parce que nous n'osons pas qu'elles sont difficiles.",
    author: "Seneque"
  },
  {
    text: "Pendant que nous remettons a plus tard, la vie passe.",
    author: "Seneque"
  },
  {
    text: "Nous souffrons plus souvent en imagination qu'en realite.",
    author: "Seneque"
  },
  {
    text: "Apprendre sans reflechir est vain ; reflechir sans apprendre est dangereux.",
    author: "Confucius"
  },
  {
    text: "Notre plus grande gloire n'est pas de ne jamais tomber, mais de nous relever a chaque chute.",
    author: "Confucius"
  },
  {
    text: "L'homme de bien exige tout de lui-meme ; l'homme mediocre attend tout des autres.",
    author: "Confucius"
  },
  {
    text: "Un voyage de mille lieues commence toujours par un premier pas.",
    author: "Lao Tseu"
  },
  {
    text: "Sur le plus haut trone du monde, on n'est jamais assis que sur son propre fondement.",
    author: "Montaigne"
  },
  {
    text: "La lecture de tous les bons livres est comme une conversation avec les meilleurs esprits des siecles passes.",
    author: "Rene Descartes"
  },
  {
    text: "Je pense, donc je suis.",
    author: "Rene Descartes"
  },
  {
    text: "Le coeur a ses raisons que la raison ne connait point.",
    author: "Blaise Pascal"
  },
  {
    text: "Ne pas se moquer, ne pas deplorer, ne pas detester, mais comprendre.",
    author: "Baruch Spinoza"
  },
  {
    text: "Traite l'humanite, en toi et en autrui, toujours comme une fin et jamais seulement comme un moyen.",
    author: "Immanuel Kant"
  },
  {
    text: "Deux choses remplissent l'ame d'admiration : le ciel etoile au-dessus de moi et la loi morale en moi.",
    author: "Immanuel Kant"
  },
  {
    text: "L'attention est la forme la plus rare et la plus pure de la generosite.",
    author: "Simone Weil"
  },
  {
    text: "La joie est le signe de l'accord avec ce qui est vrai et juste.",
    author: "Simone Weil"
  },
  {
    text: "L'enfance a ses manieres de voir, de penser et de sentir ; rien n'est moins sage que d'y vouloir substituer les notres.",
    author: "Jean-Jacques Rousseau"
  },
  {
    text: "Aide-moi a faire seul.",
    author: "Maria Montessori"
  },
  {
    text: "L'education est un processus naturel chez l'enfant ; il ne s'acquiert pas par les mots, mais par l'experience du milieu.",
    author: "Maria Montessori"
  },
  {
    text: "Etudier n'est pas un acte de consommer des idees, mais de les creer et de les recreer.",
    author: "Paulo Freire"
  },
  {
    text: "Mal nommer les choses, c'est ajouter au malheur du monde.",
    author: "Albert Camus"
  },
  {
    text: "Au milieu de l'hiver, j'apprenais enfin qu'il y avait en moi un ete invincible.",
    author: "Albert Camus"
  },
  {
    text: "L'opinion pense mal ; elle ne pense pas.",
    author: "Gaston Bachelard"
  },
  {
    text: "La connaissance du reel est une lumiere qui projette toujours quelque part des ombres.",
    author: "Gaston Bachelard"
  },
  {
    text: "L'oeil ne voit que ce que l'esprit est pret a comprendre.",
    author: "Henri Bergson"
  },
  {
    text: "Rien n'est plus dangereux qu'une idee, quand on n'a qu'une idee.",
    author: "Alain"
  },
  {
    text: "Il n'est pas signe de bonne sante d'etre bien adapte a une societe profondement malade.",
    author: "Jiddu Krishnamurti"
  },
  {
    text: "Chaque enfant qu'on enseigne est un homme qu'on gagne.",
    author: "Victor Hugo"
  },
  {
    text: "Celui qui ouvre une ecole ferme une prison.",
    author: "Victor Hugo"
  },
  {
    text: "L'education est l'arme la plus puissante pour changer le monde.",
    author: "Nelson Mandela"
  },
  {
    text: "Un enfant, un enseignant, un livre et un stylo peuvent changer le monde.",
    author: "Malala Yousafzai"
  },
  {
    text: "Pour ce qui est de l'avenir, il ne s'agit pas de le prevoir, mais de le rendre possible.",
    author: "Antoine de Saint-Exupery"
  },
  {
    text: "Le seul homme instruit est celui qui a appris comment apprendre et changer.",
    author: "Carl Rogers"
  },
  {
    text: "Il faut tout un village pour elever un enfant.",
    author: "Proverbe africain"
  },
  {
    text: "La patience est l'art d'esperer.",
    author: "Vauvenargues"
  },
  {
    text: "Nul vent n'est favorable a celui qui ne sait ou il va.",
    author: "Seneque"
  },
  {
    text: "Le doute est le commencement de la sagesse.",
    author: "Aristote"
  },
  {
    text: "On ne decouvre pas de terre nouvelle sans consentir a perdre de vue le rivage.",
    author: "Andre Gide"
  },
  {
    text: "Le vrai signe de l'intelligence, ce n'est pas la connaissance, mais l'imagination.",
    author: "Albert Einstein"
  },
  {
    text: "La simplicite est la sophistication supreme.",
    author: "Leonard de Vinci"
  },
  {
    text: "Ce n'est pas l'eleve qui est en difficulte : c'est le chemin qui doit etre ajuste.",
    author: "Pedagogie active"
  },
  {
    text: "Apprendre, c'est relier ce que l'on sait a ce que l'on vit.",
    author: "Reflexion pedagogique"
  },
  {
    text: "Prendre le temps de comprendre, c'est deja progresser.",
    author: "Reflexion pedagogique"
  },
  {
    text: "Un esprit calme apprend mieux qu'un esprit presse.",
    author: "Reflexion pedagogique"
  },
  {
    text: "Le bien-etre en classe n'est pas un luxe : c'est une condition d'apprentissage.",
    author: "Reflexion pedagogique"
  },
  {
    text: "L'erreur est un passage, pas une impasse.",
    author: "Reflexion pedagogique"
  },
  {
    text: "Chaque question bien posee ouvre deja une partie de la reponse.",
    author: "Reflexion pedagogique"
  },
  {
    text: "Former, c'est eclairer sans ecraser.",
    author: "Reflexion pedagogique"
  }
];

interface ConversionOverlayProps {
  progress: number;
  phase: "generate" | "export";
  format?: ExportFormat;
}

const PROGRESS_STAGES = [
  { value: 25, delay: 800 },
  { value: 50, delay: 4000 },
  { value: 75, delay: 9000 },
  { value: 99, delay: 15000 },
];

const STAGE_LABELS: Record<number, string> = {
  25: "Initialisation...",
  50: "Traitement en cours...",
  75: "Finalisation...",
  99: "Presque termine...",
};

export function ConversionOverlay({ progress, phase, format }: ConversionOverlayProps) {
  const [displayProgress, setDisplayProgress] = useState(4);
  const [quoteIndex, setQuoteIndex] = useState(0);

  // Simulated milestone progress (backend progress unreliable)
  useEffect(() => {
    const timers = PROGRESS_STAGES.map(({ value, delay }) =>
      window.setTimeout(() => setDisplayProgress(value), delay)
    );
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, []);

  // If real backend reports completion (100), snap immediately
  useEffect(() => {
    if (progress >= 100) setDisplayProgress(100);
  }, [progress]);

  useEffect(() => {
    const pickNext = (current: number): number => {
      if (PEDAGOGICAL_QUOTES.length <= 1) return 0;
      let next = current;
      while (next === current) next = Math.floor(Math.random() * PEDAGOGICAL_QUOTES.length);
      return next;
    };
    setQuoteIndex((current) => pickNext(current));
    const timer = window.setInterval(() => {
      setQuoteIndex((current) => pickNext(current));
    }, 9600);
    return () => window.clearInterval(timer);
  }, []);

  const isGenerate = phase === "generate";
  const title = isGenerate ? "Generation pedagogique en cours" : "Export en cours";
  const subtitle = isGenerate
    ? "Nous preparons vos activites. Prenez un court temps de reflexion."
    : `Preparation du fichier ${FORMAT_LABELS[format ?? "docx"]}...`;
  const chipLabel = isGenerate ? "Generation en cours" : "Conversion en cours";
  const activeQuote = PEDAGOGICAL_QUOTES[quoteIndex];
  const stageLabel = STAGE_LABELS[displayProgress] ?? "Traitement en cours...";

  return (
    <aside className="conversion-overlay" role="status" aria-live="polite" aria-label="Conversion en cours">
      <div className="conversion-card animate-fadeInUp">
        <div className="conversion-chip">{chipLabel}</div>
        <h3 className="mt-3 text-2xl font-semibold text-slate-900">{title}</h3>
        <p className="mt-1 text-base text-slate-700">{subtitle}</p>

        <div className="quote-stage" aria-live="polite">
          <div className="quote-stage-badge">Pause reflexion</div>
          <blockquote className="quote-stage-text">{activeQuote.text}</blockquote>
          <p className="quote-stage-author">- {activeQuote.author}</p>
        </div>

        <div className="mt-4 flex items-center justify-between text-sm font-semibold text-slate-600">
          <span>{stageLabel}</span>
          <span>{displayProgress}%</span>
        </div>
        <div className="conversion-progress-track mt-1">
          <span
            className="conversion-progress-bar"
            style={{ width: `${Math.max(4, displayProgress)}%`, transition: "width 1.2s cubic-bezier(0.4,0,0.2,1)" }}
          />
        </div>

        <div className="mt-3 flex justify-between">
          {PROGRESS_STAGES.map(({ value }) => (
            <div key={value} className="flex flex-col items-center gap-1">
              <div className={`h-2 w-2 rounded-full transition-all duration-500 ${displayProgress >= value ? "bg-teal-500 scale-125" : "bg-slate-200"}`} />
              <span className={`text-[0.65rem] font-bold transition-colors duration-500 ${displayProgress >= value ? "text-teal-600" : "text-slate-300"}`}>
                {value}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
