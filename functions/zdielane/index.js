// Záloha pre zdieľanie fotky do aplikácie, ak ešte nebeží service worker: presmeruje na úvod s tlačidlom na fotku.
export async function onRequestPost() {
  return Response.redirect('https://doplatkyliekov.sk/?akcia=foto', 303);
}
export async function onRequestGet() {
  return Response.redirect('https://doplatkyliekov.sk/', 302);
}
