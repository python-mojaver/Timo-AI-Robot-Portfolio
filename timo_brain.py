"""Central event-driven brain for Timo."""
import queue
import threading
import time
from enum import Enum


class BrainState(str, Enum):
    IDLE="IDLE"
    LISTENING="LISTENING"
    SPEAKING="SPEAKING"
    NAVIGATING="NAVIGATING"
    STOPPED="STOPPED"


class TimoBrain:
    def __init__(self, action_callback=None):
        self.action_callback=action_callback
        self.state=BrainState.IDLE
        self.events=queue.Queue()
        self.running=False
        self.worker=None
        self.recognized_people=set()

        self.people={
            "Mojaver":{"display_name":"آقای مجاور","greeting":"سلام آقای مجاور، خوب هستید؟"},
            "Khodivzad":{"display_name":"آقای خدیوزاد","greeting":"سلام آقای خدیوزاد، وقت بخیر."},
        }
        self.locations={
            "KHODIVZAD_ROOM":{"display_name":"اتاق آقای خدیوزاد","robot_target":None}
        }

    def start(self):
        if self.running:
            return
        self.running=True
        self.state=BrainState.IDLE
        self.worker=threading.Thread(target=self._loop, daemon=True)
        self.worker.start()
        print("[BRAIN] Timo Brain started")

    def stop(self):
        self.running=False
        self.state=BrainState.STOPPED
        self.events.put(None)
        if self.worker and self.worker.is_alive() and threading.current_thread()!=self.worker:
            self.worker.join(timeout=2)
        print("[BRAIN] Timo Brain stopped")

    def submit_event(self, event):
        if not self.running:
            self.start()
        self.events.put(event)

    def _loop(self):
        while self.running:
            event=self.events.get()
            if event is None:
                break
            try:
                self._handle(event)
            except Exception as exc:
                print(f"[BRAIN ERROR] {type(exc).__name__}: {exc}")

    def _handle(self,event):
        event_type=str(event.get("type","")).upper()
        print(f"[BRAIN EVENT] {event}")

        if event_type=="PERSON_RECOGNIZED":
            self._person_recognized(event)
        elif event_type=="USER_SPEECH_STARTED":
            # Foundation for realtime barge-in.
            if self.state==BrainState.SPEAKING:
                self.emit_action("STOP_SPEAKING")
            self.state=BrainState.LISTENING
        elif event_type=="USER_COMMAND":
            intent=str(event.get("intent","")).upper()
            target=str(event.get("target","")).upper()
            if intent=="NAVIGATE":
                self.navigate(target)
            elif intent=="STOP":
                self.emit_action("STOP")
                self.state=BrainState.IDLE
        elif event_type=="NAVIGATION_ARRIVED":
            self.state=BrainState.IDLE
        else:
            print(f"[BRAIN] Unhandled event: {event_type}")

    def _person_recognized(self,event):
        name=str(event.get("name","")).strip()
        if not name or name in self.recognized_people:
            return
        self.recognized_people.add(name)

        person=self.people.get(name)
        if not person:
            print(f"[BRAIN] No profile for recognized person: {name}")
            return

        confidence=float(event.get("confidence",0))
        print(f"[BRAIN] Recognized {person['display_name']} ({confidence:.3f})")
        self.speak(person["greeting"])
        self.wave()
        self.listen()

    def emit_action(self,action_type,**payload):
        action={"type":action_type,"payload":payload,"timestamp":time.time()}
        print(f"[ACTION] {action}")
        if self.action_callback:
            self.action_callback(action)
        return action

    def speak(self,text):
        self.state=BrainState.SPEAKING
        return self.emit_action("SPEAK",text=text)

    def wave(self):
        return self.emit_action("WAVE")

    def listen(self):
        self.state=BrainState.LISTENING
        return self.emit_action("LISTEN")

    def navigate(self,target):
        target=target.upper()
        location=self.locations.get(target)
        if not location:
            print(f"[BRAIN] Unknown navigation target: {target}")
            return None
        self.state=BrainState.NAVIGATING
        return self.emit_action(
            "NAVIGATE",
            target=target,
            location=location["display_name"],
            robot_target=location["robot_target"],
        )


def demo_robot_bridge(action):
    # Placeholder only; real voice/Robot SDK will replace this.
    print(f"[ROBOT BRIDGE PLACEHOLDER] {action['type']} -> {action['payload']}")


if __name__=="__main__":
    brain=TimoBrain(action_callback=demo_robot_bridge)
    brain.start()

    brain.submit_event({
        "type":"PERSON_RECOGNIZED",
        "name":"Mojaver",
        "confidence":0.569,
        "timestamp":time.time(),
    })
    time.sleep(0.5)

    print("\n[DEMO] Simulating NAVIGATE -> KHODIVZAD_ROOM")
    brain.submit_event({
        "type":"USER_COMMAND",
        "intent":"NAVIGATE",
        "target":"KHODIVZAD_ROOM",
        "timestamp":time.time(),
    })
    time.sleep(0.5)
    brain.stop()
