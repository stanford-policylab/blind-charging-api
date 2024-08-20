import asyncio
import logging
from typing import NamedTuple, cast

from .enumerator import RoleEnumerator
from .generated.models import HumanName, MaskedSubject, RedactionTarget
from .name import human_name_to_str
from .store import SimpleMapping, StoreSession

logger = logging.getLogger(__name__)


SavedMask = NamedTuple("SavedMask", [("role", str), ("mask", str), ("name", str)])
"""Information about a masked annotation saved in our DB."""


class MaskInfo:
    """A collection of masks for a case."""

    def __init__(self, initial: dict[bytes, SavedMask] | None = None):
        self._masks = initial or {}

    def get(self, subject_id: bytes) -> SavedMask:
        return self._masks[subject_id]

    def set(self, subject_id: bytes, mask_info: SavedMask):
        self._masks[subject_id] = mask_info

    def get_name_mask_map(self) -> dict[str, str]:
        return {v.name: v.mask for v in self._masks.values()}

    def get_id_name_map(self) -> dict[str, str]:
        return {k.decode(): v.name for k, v in self._masks.items()}


FOUR_HOURS_S = 4 * 60 * 60
"""Four hours in seconds."""


def ensure_init(func):
    """Decorator to ensure that the case store is initialized.

    Args:
        func: The function to wrap.

    Returns:
        The wrapped function.
    """
    # Check if the func is async
    if hasattr(func, "__await__"):

        async def async_wrapper(self, *args, **kwargs):
            if not self.inited:
                raise ValueError("Case store not initialized")
            return await func(self, *args, **kwargs)

        return async_wrapper
    else:

        def sync_wrapper(self, *args, **kwargs):
            if not self.inited:
                raise ValueError("Case store not initialized")
            return func(self, *args, **kwargs)

        return sync_wrapper


class CaseStore:
    def __init__(self, store: StoreSession):
        self.store = store
        self.jurisdiction_id = ""
        self.case_id = ""
        self.expires_at = 0

    @property
    def inited(self) -> bool:
        return bool(self.jurisdiction_id and self.case_id)

    async def init(self, jurisdiction_id: str, case_id: str, ttl: int = FOUR_HOURS_S):
        """Initialize the case store.

        Args:
            jurisdiction_id (str): The jurisdiction ID.
            case_id (str): The case ID.
            ttl (int, optional): The time-to-live in seconds. Defaults to 4 hours.

        Returns:
            None
        """
        if self.inited:
            return
        self.jurisdiction_id = jurisdiction_id
        self.case_id = case_id
        self.expires_at = await self.set_expiration(ttl)
        logger.debug("CaseStore initialized, will expire at %d", self.expires_at)

    @ensure_init
    async def set_expiration(self, ttl: int) -> int:
        """Set the expiration time for the case.

        Returns:
            int: The expiration time, as a unix timestamp
        """
        expires_at = await self.store.time() + ttl
        k = self.key("expires")
        await self.store.set(k, "")
        await self.store.expire_at(k, expires_at)
        return expires_at

    @ensure_init
    async def get_masked_names(self) -> list[MaskedSubject]:
        """Get the aliases for a case.

        Returns:
            list[MaskedSubject]: The masked subjects.
        """
        masks = await self.store.hgetall(self.key("mask"))
        return [MaskedSubject(subjectId=k, alias=v or "") for k, v in masks.items()]

    @ensure_init
    async def save_masked_name(self, subject_id: str, mask: str) -> None:
        """Save a masked name for a subject.

        Returns:
            None
        """
        mapping_key = self.key("mask")
        await self.store.hsetmapping(mapping_key, {subject_id: mask})

    @ensure_init
    async def save_roles(
        self,
        subject_role_mapping: dict[str, str],
    ) -> None:
        """Save the roles for a case.

        Args:
            subject_role_mapping (dict[str, str]): The subject role mapping

        Returns:
            None
        """
        # dict[str, str] is not a strict subtype of Mapping[str | bytes, str | bytes],
        # even though it is fully compatible.
        # https://stackoverflow.com/a/72841649
        srm = cast(SimpleMapping, subject_role_mapping)
        k = self.key("role")
        await self.store.hsetmapping(k, srm)
        await self.store.expire_at(k, self.expires_at)

    @ensure_init
    async def get_mask_info(self) -> MaskInfo:
        """Get information about masks for a case.

        Returns:
            MaskInfo: Description of all masks for a case.
        """
        # id_to_role
        # ---
        # A map from subject ID to role, e.g.:
        # {"1": "judge", "2": "attorney"}
        #
        # id_to_mask
        # ---
        # A map from subject ID to an enumerated role used in the redacted text, e.g.:
        # {"1": "judge 1", "2": "attorney 1"}
        id_to_role, id_to_mask = await asyncio.gather(
            self.store.hgetall(self.key("role")),
            self.store.hgetall(self.key("mask")),
        )
        # Every subject ID in the case that we are tracking, e.g.:
        # ["1", "2"]
        all_ids_list = list(id_to_role.keys() | id_to_mask.keys())
        # The primary name for each subject ID, e.g.:
        # ["John Doe", "Jane Doe"]
        all_names_list = await asyncio.gather(
            *[
                self.store.getmodel(
                    HumanName, self.key(f"aliases:{subject_id.decode()}:primary")
                )
                for subject_id in all_ids_list
            ]
        )
        # Map from subject ID to real primary name, e.g.:
        # {"1": "John Doe", "2": "Jane Doe"}
        id_to_real_name = {
            k: human_name_to_str(v)
            for k, v in dict(zip(all_ids_list, all_names_list)).items()
            if v
        }
        # The subject IDs that we know about roles but don't have masks for yet.
        ids_missing_masks = id_to_role.keys() - id_to_mask.keys()

        # Start generating final metadata, e.g.:
        # MaskInfo({
        #   "j1": SavedMask(role="judge", mask="Judge 1", name="John Doe"),
        #   "a1": SavedMask(role="attorney", mask="Attorney 1", name="Jane Doe"),
        # })
        #
        # First, add the names that we have explicit masks and names for.
        metadata = MaskInfo(
            {
                k: SavedMask(
                    name=id_to_real_name.get(k, ""),
                    role=id_to_role.get(k, b"").decode(),
                    mask=id_to_mask.get(k, b"").decode(),
                )
                for k in id_to_mask.keys()
                if k in id_to_real_name
            }
        )

        # Next, create a RoleEnumerator so that we can generate masks for everyone else.
        try:
            role_enumerator = RoleEnumerator(v.decode() for v in id_to_mask.values())
        except ValueError as e:
            logger.error("Error initializing RoleEnumerator: %s", e)
            role_enumerator = RoleEnumerator()

        # Generate masks for the remaining IDs.
        for subject_id in ids_missing_masks:
            real_name = id_to_real_name.get(subject_id, "")
            mask = role_enumerator.next_mask(id_to_role[subject_id].decode())
            metadata.set(
                subject_id,
                SavedMask(
                    name=real_name,
                    role=id_to_role[subject_id].decode(),
                    mask=mask,
                ),
            )

        return metadata

    @ensure_init
    async def get_doc_tasks(self) -> dict[str, str]:
        """Get the document tasks for a case.

        Returns:
            dict[str, str]: The document tasks.
        """
        result = await self.store.hgetall(self.key("task"))
        return {k.decode(): v.decode() for k, v in result.items()}

    @ensure_init
    async def save_doc_task(self, doc_id: str, task_id: str) -> None:
        """Save a document task ID.

        Args:
            doc_id (str): The document ID.
            task_id (str): The task ID.

        Returns:
            None
        """
        k = self.key("task")
        await self.store.hsetmapping(
            k,
            {doc_id: str(task_id)},
        )
        await self.store.expire_at(k, self.expires_at)

    @ensure_init
    async def save_objects_list(self, objects: list[RedactionTarget]):
        """Save the objects list for a case.

        Args:
            objects (list[RedactionTarget]): The objects.

        Returns:
            None
        """
        k = self.key("objects")
        for obj in objects:
            await self.store.enqueue_model(k, obj)
        await self.store.expire_at(k, self.expires_at)

    @ensure_init
    async def pop_object(self) -> RedactionTarget | None:
        """Pop an object from the objects list.

        Returns:
            RedactionTarget: The object.
        """
        k = self.key("objects")
        obj = await self.store.dequeue_model(RedactionTarget, k)
        return obj

    @ensure_init
    async def save_real_name(
        self, subject_id: str, alias: HumanName, primary: bool = False
    ) -> None:
        """Save a real name for a subject.

        Args:
            subject_id (str): The subject ID.
            alias (HumanName): The alias.
            primary (bool, optional): Whether the alias is primary. Defaults to False.

        Returns:
            None
        """
        subject_key = f"aliases:{subject_id}"

        if primary:
            k = self.key(f"{subject_key}:primary")
            await self.store.setmodel(k, alias)
            await self.store.expire_at(k, self.expires_at)

        await self.store.saddmodel(self.key(subject_key), alias)
        await self.store.expire_at(self.key(subject_key), self.expires_at)

    @ensure_init
    def key(self, category: str) -> str:
        """Generate a key for a redis value.

        Args:
            category (str): The category of the task.

        Returns:
            str: The key.
        """
        return f"{self.jurisdiction_id}:{self.case_id}:{category}"
