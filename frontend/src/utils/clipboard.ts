/**
 * Copy text to clipboard with iOS fallback.
 * Returns true if the copy succeeded, false otherwise.
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  // Try the modern Clipboard API first
  if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Fall through to legacy fallback
    }
  }

  // Legacy fallback for iOS Safari and older browsers
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;

    // Prevent scrolling on iOS
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    textarea.style.top = "-9999px";
    textarea.style.opacity = "0";

    document.body.appendChild(textarea);

    // iOS-specific selection
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
    if (isIOS) {
      const range = document.createRange();
      range.selectNodeContents(textarea);
      const selection = window.getSelection();
      if (selection) {
        selection.removeAllRanges();
        selection.addRange(range);
      }
      textarea.setSelectionRange(0, text.length);
    } else {
      textarea.select();
    }

    const success = document.execCommand("copy");
    document.body.removeChild(textarea);
    return success;
  } catch {
    return false;
  }
}
