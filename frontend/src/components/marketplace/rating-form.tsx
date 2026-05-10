"use client";

/**
 * Star + review form. Only visible when the caller is an active
 * subscriber of the listing. Submits via POST /ratings on first
 * submit, PUT /ratings/{rid} on subsequent edits.
 */

import { useState } from "react";
import { motion } from "framer-motion";
import { Loader2, Send, Star } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Input } from "@/components/ui/input";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface RatingFormProps {
  listingId: string;
  existingRating: { id: string; rating: number; review: string | null } | null;
  onSubmitted: () => void;
}

export function RatingForm({
  listingId,
  existingRating,
  onSubmitted,
}: RatingFormProps) {
  const [stars, setStars] = useState(existingRating?.rating ?? 0);
  const [review, setReview] = useState(existingRating?.review ?? "");
  const [submitting, setSubmitting] = useState(false);

  const isUpdate = existingRating != null;

  async function handleSubmit() {
    if (stars < 1 || stars > 5) {
      toast.error("1-5 stars chuno");
      return;
    }
    setSubmitting(true);
    try {
      const body = { rating: stars, review: review.trim() || null };
      if (isUpdate) {
        await api.put(
          `/marketplace/listings/${listingId}/ratings/${existingRating.id}`,
          body,
        );
        toast.success("Rating update ho gayi 🎉");
      } else {
        await api.post(`/marketplace/listings/${listingId}/ratings`, body);
        toast.success("Rating submit ho gayi 🎉");
      }
      onSubmitted();
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : "Rating submit nahi ho payi";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <GlassmorphismCard hover={false}>
      <div className="space-y-3">
        <header>
          <h3 className="text-sm font-semibold">
            {isUpdate ? "Update your rating" : "Rate this strategy"}
          </h3>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            Aapne subscribe kiya hai — ab community ko apna feedback bhi de do.
          </p>
        </header>

        <div className="flex items-center gap-1.5">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => setStars(n)}
              aria-label={`${n} star${n === 1 ? "" : "s"}`}
              className="transition-transform hover:scale-110"
            >
              <Star
                className={cn(
                  "h-6 w-6 transition-colors",
                  n <= stars
                    ? "fill-amber-300 text-amber-300"
                    : "text-muted-foreground/40",
                )}
              />
            </button>
          ))}
          <span className="text-[11px] text-muted-foreground ml-2">
            {stars > 0 ? `${stars} / 5` : "Stars chuno"}
          </span>
        </div>

        <div className="space-y-1.5">
          <label
            htmlFor={`review-${listingId}`}
            className="text-[10px] uppercase tracking-wide text-muted-foreground"
          >
            Review (optional)
          </label>
          <Input
            id={`review-${listingId}`}
            value={review}
            onChange={(e) => setReview(e.target.value)}
            placeholder="Strategy ke baare mein kya kahoge?"
            maxLength={4000}
          />
        </div>

        <motion.div
          whileTap={{ scale: 0.98 }}
          className="flex justify-end"
        >
          <Button
            variant="outline"
            size="sm"
            onClick={handleSubmit}
            disabled={submitting || stars === 0}
            type="button"
          >
            {submitting ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5" />
            )}
            {isUpdate ? "Update Rating" : "Submit Rating"}
          </Button>
        </motion.div>
      </div>
    </GlassmorphismCard>
  );
}
