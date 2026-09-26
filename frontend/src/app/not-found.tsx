import Link from "next/link";

/**
 * The page a customer lands on when a link is wrong or old (founder's rule, 26 Sep:
 * "errors in human words … never a dead end"). Before this file existed the live
 * site showed Next.js's default "404: This page could not be found." — English,
 * a status code, and no way back.
 */
export default function NotFound() {
  return (
    <main className="min-h-[70vh] flex items-center justify-center p-6">
      <div className="max-w-md w-full space-y-4 text-center">
        <h1 className="text-2xl font-bold">Yeh page nahi mila</h1>
        <p className="text-base text-muted-foreground leading-relaxed">
          Link galat ya purana ho sakta hai. Aapka account aur settings bilkul theek hain — bas yeh
          address kisi page par nahi jaata. Neeche wale button se shuru ke page par chalo.
        </p>
        <div className="flex flex-col gap-2 pt-2">
          <Link
            href="/"
            className="inline-flex min-h-12 items-center justify-center rounded-md bg-primary px-4 text-base font-medium text-primary-foreground"
          >
            Shuru ke page par jao
          </Link>
          <Link
            href="/contact"
            className="inline-flex min-h-11 items-center justify-center rounded-md border border-border px-4 text-sm"
          >
            Samajh na aaye to hume WhatsApp karo
          </Link>
        </div>
      </div>
    </main>
  );
}
