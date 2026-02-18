export const srtToVtt = (srt: string) => {
  const body = srt
    .replaceAll("\r\n", "\n")
    .replaceAll(/(\d{2}:\d{2}:\d{2}),(\d{3})/g, "$1.$2");

  return `WEBVTT\n\n${body}`;
};
