import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

vi.mock("next/image", () => {
  const MockImage = (props: {
    src?: string;
    alt?: string;
    className?: string;
    width?: number | string;
    height?: number | string;
    fill?: boolean;
    sizes?: string;
    priority?: boolean;
    quality?: number | string;
    style?: React.CSSProperties;
    onLoad?: () => void;
    onError?: () => void;
  }) => {
    const { src, alt, width, height, fill, style, ...rest } = props;
    const finalWidth = fill ? undefined : Number(width) || undefined;
    const finalHeight = fill ? undefined : Number(height) || undefined;
    return (
      <img
        src={typeof src === "string" ? src : ""}
        alt={alt ?? ""}
        width={finalWidth}
        height={finalHeight}
        style={style}
        {...rest}
      />
    );
  };
  MockImage.displayName = "next/image";
  return { default: MockImage };
});

afterEach(() => {
  cleanup();
});
