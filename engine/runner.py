"""Agent runner: loads configs, creates triggers, executes action pipelines."""

import logging
import os
import threading
import time
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
from engine.triggers.scheduled import ScheduledTrigger
from engine.triggers.polling import PollingTrigger
from engine.triggers.manual import ManualTrigger
from engine.actions import llm_analyze, notify_telegram, http_request

logger = logging.getLogger(__name__)


class AgentInstance:
    """A single running agent with its trigger and action pipeline."""

    def __init__(self, config: Dict[str, Any], llm):
        self.config = config
        self.name: str = config.get("name", "unnamed")
        self.description: str = config.get("description", "")
        self.llm = llm
        self.actions: List[Dict] = config.get("actions", [])
        self.running = True
        self.last_run: Optional[float] = None
        self.run_count = 0

        trigger_config = config.get("trigger", {})
        trigger_type = trigger_config.get("type", "manual")

        if trigger_type == "scheduled":
            self.trigger = ScheduledTrigger(trigger_config, self._on_trigger)
        elif trigger_type == "polling":
            self.trigger = PollingTrigger(trigger_config, self._on_trigger)
        else:
            self.trigger = ManualTrigger(trigger_config, self._on_trigger)

    def _on_trigger(self, trigger_data: Dict[str, Any]) -> None:
        """Execute the action pipeline when the trigger fires."""
        variables = dict(trigger_data)
        logger.info("Agent '%s' triggered, running %d actions", self.name, len(self.actions))

        for i, action in enumerate(self.actions):
            a_type = action.get("type", "")
            try:
                if a_type == "llm_analyze":
                    variables = llm_analyze.execute(action, variables, self.llm)
                elif a_type == "notify_telegram":
                    variables = notify_telegram.execute(action, variables)
                elif a_type == "http_request":
                    variables = http_request.execute(action, variables)
                else:
                    logger.warning("Unknown action type: %s", a_type)
            except Exception as e:
                logger.error("Agent '%s' action %d (%s) failed: %s", self.name, i, a_type, e)

        self.last_run = time.time()
        self.run_count += 1

    def manual_fire(self) -> None:
        """Manually trigger the agent."""
        self.trigger.fire()


class AgentRunner:
    """Manages all running agents. Handles scheduling, loading, and lifecycle."""

    def __init__(self, llm, configs_dir: Optional[Path] = None):
        self.llm = llm
        self.configs_dir = configs_dir or Path(os.path.dirname(os.path.abspath(__file__))).parent / "configs"
        self.configs_dir.mkdir(parents=True, exist_ok=True)
        self.agents: Dict[str, AgentInstance] = {}
        self._scheduler_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def add_agent(self, config: Dict[str, Any]) -> str:
        """Add and start an agent from a config dict. Returns agent name."""
        name = config.get("name", "unnamed")
        self._save_config(name, config)
        agent = AgentInstance(config, self.llm)
        self.agents[name] = agent
        logger.info("Agent '%s' added and running", name)
        return name

    def remove_agent(self, name: str) -> bool:
        """Stop and remove an agent. Returns True if found."""
        if name in self.agents:
            self.agents[name].running = False
            del self.agents[name]
            config_file = self.configs_dir / f"{name}.yaml"
            if config_file.exists():
                config_file.unlink()
            logger.info("Agent '%s' removed", name)
            return True
        return False

    def manual_trigger(self, name: str) -> bool:
        """Manually fire an agent's trigger. Returns True if found."""
        if name in self.agents:
            self.agents[name].manual_fire()
            return True
        return False

    def list_agents(self) -> List[Dict[str, Any]]:
        """Return info about all running agents."""
        result = []
        for name, agent in self.agents.items():
            trigger = agent.config.get("trigger", {})
            result.append({
                "name": name,
                "description": agent.description,
                "trigger_type": trigger.get("type", "unknown"),
                "interval_minutes": trigger.get("interval_minutes", 0),
                "run_count": agent.run_count,
                "running": agent.running,
            })
        return result

    def get_config(self, name: str) -> Optional[Dict[str, Any]]:
        """Return the config for a named agent."""
        if name in self.agents:
            return self.agents[name].config
        return None

    def start_scheduler(self) -> None:
        """Start the background scheduler thread that fires triggers on interval."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            return
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        logger.info("Scheduler started")

    def stop_scheduler(self) -> None:
        """Stop the background scheduler."""
        self._stop_event.set()

    def _scheduler_loop(self) -> None:
        """Main scheduler loop. Checks each agent's trigger at its interval."""
        counters: Dict[str, int] = {}
        while not self._stop_event.is_set():
            for name, agent in list(self.agents.items()):
                if not agent.running:
                    continue
                interval = getattr(agent.trigger, "interval_minutes", 0)
                if interval <= 0:
                    continue
                tick = counters.get(name, 0) + 1
                counters[name] = tick
                if tick >= interval:
                    counters[name] = 0
                    try:
                        agent.trigger.fire()
                    except Exception as e:
                        logger.error("Trigger fire failed for '%s': %s", name, e)
            self._stop_event.wait(60)

    def load_saved_configs(self) -> int:
        """Load all YAML configs from the configs directory. Returns count loaded."""
        count = 0
        for f in self.configs_dir.glob("*.yaml"):
            try:
                config = yaml.safe_load(f.read_text(encoding="utf-8"))
                if isinstance(config, dict) and "name" in config:
                    agent = AgentInstance(config, self.llm)
                    self.agents[config["name"]] = agent
                    count += 1
            except Exception as e:
                logger.warning("Failed to load config %s: %s", f.name, e)
        logger.info("Loaded %d saved agent configs", count)
        return count

    def _save_config(self, name: str, config: Dict[str, Any]) -> None:
        """Persist a config to disk."""
        path = self.configs_dir / f"{name}.yaml"
        path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False), encoding="utf-8")
