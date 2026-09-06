/**
 * Moved. The indicator catalog and the educational glossary were two pages
 * listing different things; they are now ONE page at /indicators, with the API
 * catalog as the source and the guides as its detail.
 */
import { redirect } from "next/navigation";

export default function MovedIndicatorLibrary() {
  redirect("/indicators");
}
