import logging

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("PulseAlpha Worker starting")
    logger.info("LangGraph analysis graph available — use worker.graph.run_analysis()")


if __name__ == "__main__":
    main()
