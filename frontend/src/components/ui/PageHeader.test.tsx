import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ImageCard, PageHeader } from "./index";

describe("PageHeader", () => {
  it("renders eyebrow, heading, and description", () => {
    render(
      <PageHeader
        eyebrow="Inicio"
        heading="Cuida tus plantas"
        description="Asistente botánico para tu jardín."
        actions={<a href="/welcome">Comenzar</a>}
      />,
    );
    expect(screen.getByText("Inicio")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { level: 1, name: "Cuida tus plantas" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Asistente botánico para tu jardín."),
    ).toBeInTheDocument();
  });
});

describe("ImageCard", () => {
  it("renders title, description, and meta slot", () => {
    render(
      <ImageCard
        eyebrow="Identificar"
        title="Empezá por una foto"
        description="Subí o tomá una foto de tu planta."
        meta={<span>Próximamente</span>}
      />,
    );
    expect(
      screen.getByRole("heading", { level: 3, name: "Empezá por una foto" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Subí o tomá una foto de tu planta."),
    ).toBeInTheDocument();
    expect(screen.getByText("Próximamente")).toBeInTheDocument();
  });

  it("renders the fallback surface when no image is provided", () => {
    const { container } = render(<ImageCard title="Sin imagen" />);
    expect(container.querySelector('[aria-hidden="true"]')).toBeInTheDocument();
  });
});
