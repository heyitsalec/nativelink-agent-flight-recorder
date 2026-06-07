import type { ComponentProps } from "../../view/types";

export function parseListProp(value: string | number | boolean | null | undefined): string[] {
  if (typeof value !== "string" || !value.trim()) return [];
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

export function boolProp(props: ComponentProps | undefined, key: string, defaultValue = false): boolean {
  const value = props?.[key];
  if (typeof value === "boolean") return value;
  if (value === "true") return true;
  if (value === "false") return false;
  return defaultValue;
}

export function stringProp(
  props: ComponentProps | undefined,
  key: string,
  defaultValue = "",
): string {
  const value = props?.[key];
  return typeof value === "string" ? value : defaultValue;
}
