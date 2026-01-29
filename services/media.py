from pathlib import Path
import ffmpeg


class MediaProcessor:
    @staticmethod
    def extract_audio(input_file: Path) -> Path:
        output_file = input_file.with_suffix(".opus")
        ffmpeg.input(str(input_file)).output(
            str(output_file),
            ac=1,
            ar="16000",
            audio_bitrate="24k",
        ).run()
        return output_file
