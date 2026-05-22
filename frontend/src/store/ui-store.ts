import { create } from "zustand";

type UiState = {
  activeModal: string | null;
  setActiveModal: (modal: string | null) => void;
};

export const useUiStore = create<UiState>((set) => ({
  activeModal: null,
  setActiveModal: (activeModal) => set({ activeModal }),
}));
