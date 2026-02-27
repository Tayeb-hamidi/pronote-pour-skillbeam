"use client";

import clsx from "clsx";
import Image from "next/image";

export function PronoteLogoIcon({ className }: { className?: string }) {
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

export function EleaLogoIcon({ className }: { className?: string }) {
    return <Image src="/elea-logo.png" alt="Logo Elea" width={340} height={107} className={className} />;
}
