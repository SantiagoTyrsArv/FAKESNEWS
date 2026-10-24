// Tells the first mount of the document apart from client navigations. The
// root template marks it mounted in its layout effect; anything rendered in
// the same first pass (the page, its hooks) still reads "document load".
let documentMounted = false;

export function isDocumentLoad(): boolean {
  return !documentMounted;
}

export function markDocumentMounted(): void {
  documentMounted = true;
}
