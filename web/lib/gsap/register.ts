/**
 * The single import point for GSAP across the codebase (architecture §5.1).
 * Importing gsap or any plugin from anywhere else is forbidden — this keeps
 * plugin registration impossible to forget and tree-shaking predictable.
 */
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";
import { Flip } from "gsap/Flip";
import { MotionPathPlugin } from "gsap/MotionPathPlugin";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { SplitText } from "gsap/SplitText";

if (typeof window !== "undefined") {
  gsap.registerPlugin(useGSAP, ScrollTrigger, Flip, MotionPathPlugin, SplitText);
}

export { Flip, gsap, MotionPathPlugin, ScrollTrigger, SplitText, useGSAP };
