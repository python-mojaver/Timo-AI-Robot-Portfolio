import speech_recognition as sr


def listen():
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("🎤 صحبت کنید...")

        recognizer.adjust_for_ambient_noise(
            source,
            duration=0.5
        )

        audio = recognizer.listen(source)

    try:
        text = recognizer.recognize_google(
            audio,
            language="fa-IR"
        )

        print("متن تشخیص داده شده:", text)

        return text

    except sr.UnknownValueError:
        print("متوجه صحبت نشدم.")
        return None

    except sr.RequestError as error:
        print("خطای سرویس تشخیص صدا:", error)
        return None


if __name__ == "__main__":
    listen()