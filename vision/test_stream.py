import cv2

cap = cv2.VideoCapture("timo_stream.mjpg")

if not cap.isOpened():
    print("ERROR: Could not open Timo stream")
    exit()

print("Timo stream opened successfully")

while True:
    ret, frame = cap.read()

    if not ret:
        print("End of stream")
        break

    cv2.imshow("Timo Camera", frame)

    if cv2.waitKey(30) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()