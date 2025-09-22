import base64
import os


class LogoEncoder:
    def __init__(self, filepath, savepath):
        self.filepath = filepath
        self.savepath = savepath

    def image_to_base64(self):
        """Convert image file to Base64 string."""
        if not os.path.exists(self.filepath):
            raise FileNotFoundError(f"⚠️ File not found: {self.filepath}")
        with open(self.filepath, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def save_base64(self):
        """Convert and save Base64 string to file."""
        base64_string = self.image_to_base64()

        # Preview in console (first 200 chars only)
        print("🔍 Preview of Base64 string:")
        print(base64_string[:200], "...")

        # Save full string to file
        with open(self.savepath, "w", encoding="utf-8") as f:
            f.write(base64_string)

        print(f"📂 Saved to: {self.savepath}")
        print("✅ Logo successfully converted to Base64!\n")
        return base64_string


if __name__ == "__main__":
    # Input image path (Gemini generated logo)
    logo_filepath = r"C:\Users\Useless\Desktop\final erp\modules\Gemini_Generated_Image_eux007eux007eux0.png"
    # Output file path
    save_filepath = r"C:\Users\Useless\Desktop\final erp\logo_base64.txt"

    encoder = LogoEncoder(logo_filepath, save_filepath)
    encoder.save_base64()
