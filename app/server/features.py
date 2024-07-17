from alligater import Alligater, Arm, Feature, Population, PrintLogger, Rollout, Variant

gater = Alligater(
    logger=PrintLogger(),
    features=[
        Feature(
            "ft_blind_review",
            variants=[
                Variant("blind", True),
                Variant("control", False),
            ],
            rollouts=[
                Rollout(
                    name=Rollout.DEFAULT,
                    population=Population.DEFAULT,
                    arms=[
                        Arm("blind", weight=0.5),
                        Arm("control", weight=0.5),
                    ],
                    sticky=False,
                ),
            ],
        ),
    ],
)
