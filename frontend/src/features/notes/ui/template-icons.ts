import type { ComponentType } from "react";

import {
  Briefcase,
  CalendarDays,
  ChartColumn,
  Handshake,
  Landmark,
  Lightbulb,
  Magnet,
  Phone,
  Rocket,
  Users,
} from "lucide-react";

import type { TemplateIcon } from "../domain/templates";
import { EnhancedNotesIcon } from "./enhanced-notes-icon";

/* The icons a template can have, as boards have theirs; the `notesTemplates` catalog names each one. */

export const TEMPLATE_ICON_GLYPHS: Record<TemplateIcon, ComponentType<{ className?: string }>> = {
  enhanced: EnhancedNotesIcon,
  briefcase: Briefcase,
  chart: ChartColumn,
  handshake: Handshake,
  landmark: Landmark,
  lightbulb: Lightbulb,
  magnet: Magnet,
  phone: Phone,
  rocket: Rocket,
  calendar: CalendarDays,
  users: Users,
};
