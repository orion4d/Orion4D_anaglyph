# ============================================================================
# orion4d_anaglyph.py
# Custom Node ComfyUI - Depth-based Stereo Anaglyph
# ============================================================================

import torch
import torch.nn.functional as F


class Orion4D_DepthAnaglyph:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "depth_map": ("IMAGE",),

                "strength": ("FLOAT", {
                    "default": 24.0,
                    "min": -256.0,
                    "max": 256.0,
                    "step": 0.5,
                    "display": "slider",
                }),

                "convergence": ("FLOAT", {
                    "default": 0.50,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "display": "slider",
                }),

                "shift_mode": ([
                    "symmetric",
                    "left_static",
                    "right_static",
                ],),

                "depth_invert": ("BOOLEAN", {"default": False}),

                "depth_blur": ("INT", {
                    "default": 3,
                    "min": 0,
                    "max": 101,
                    "step": 2,
                    "display": "slider",
                }),

                "depth_gamma": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.10,
                    "max": 5.0,
                    "step": 0.05,
                    "display": "slider",
                }),

                "depth_contrast": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.10,
                    "max": 5.0,
                    "step": 0.05,
                    "display": "slider",
                }),

                "near_clip": ("FLOAT", {
                    "default": 0.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "display": "slider",
                }),

                "far_clip": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.01,
                    "display": "slider",
                }),

                "anaglyph_mode": ([
                    "optimized_dubois_red_cyan",
                    "color_red_cyan",
                    "half_color_red_cyan",
                    "gray_red_cyan",
                    "color_red_blue",
                    "half_color_red_blue",
                    "gray_red_blue",
                ],),

                "sbs_layout": ([
                    "left_right",
                    "right_left",
                ],),

                "swap_eyes": ("BOOLEAN", {"default": False}),

                "padding_mode": ([
                    "border",
                    "reflection",
                    "zeros",
                ],),

                "interpolation": ([
                    "bilinear",
                    "bicubic",
                    "nearest",
                ],),
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "IMAGE", "IMAGE")
    RETURN_NAMES = ("anaglyph", "side_by_side", "left_view", "right_view", "processed_depth")
    FUNCTION = "generate"
    CATEGORY = "Orion4D_Anaglyph"

    def generate(
        self,
        image,
        depth_map,
        strength,
        convergence,
        shift_mode,
        depth_invert,
        depth_blur,
        depth_gamma,
        depth_contrast,
        near_clip,
        far_clip,
        anaglyph_mode,
        sbs_layout,
        swap_eyes,
        padding_mode,
        interpolation,
    ):
        image = self._ensure_bhwc(image).float().clamp(0.0, 1.0)
        depth_map = self._ensure_bhwc(depth_map).float()

        image = self._ensure_rgb(image)
        image, depth_map = self._match_batch(image, depth_map)

        _, h, w, _ = image.shape
        device = image.device
        dtype = image.dtype

        depth = self._prepare_depth(
            depth_map=depth_map.to(device=device, dtype=dtype),
            target_h=h,
            target_w=w,
            invert=depth_invert,
            blur_kernel=depth_blur,
            gamma=depth_gamma,
            contrast=depth_contrast,
            near_clip=near_clip,
            far_clip=far_clip,
        )

        parallax = (depth - float(convergence)) * float(strength)

        if shift_mode == "left_static":
            left_shift = torch.zeros_like(parallax)
            right_shift = parallax * 2.0
        elif shift_mode == "right_static":
            left_shift = -parallax * 2.0
            right_shift = torch.zeros_like(parallax)
        else:
            left_shift = -parallax
            right_shift = parallax

        if swap_eyes:
            left_shift, right_shift = right_shift, left_shift

        left_view = self._warp_horizontal(
            image=image,
            shift_px=left_shift,
            padding_mode=padding_mode,
            interpolation=interpolation,
        )

        right_view = self._warp_horizontal(
            image=image,
            shift_px=right_shift,
            padding_mode=padding_mode,
            interpolation=interpolation,
        )

        anaglyph = self._make_anaglyph(left_view, right_view, anaglyph_mode)

        if sbs_layout == "right_left":
            side_by_side = torch.cat((right_view, left_view), dim=2)
        else:
            side_by_side = torch.cat((left_view, right_view), dim=2)

        processed_depth = depth.permute(0, 2, 3, 1).repeat(1, 1, 1, 3).clamp(0.0, 1.0)

        return (
            anaglyph.clamp(0.0, 1.0),
            side_by_side.clamp(0.0, 1.0),
            left_view.clamp(0.0, 1.0),
            right_view.clamp(0.0, 1.0),
            processed_depth,
        )

    def _ensure_bhwc(self, x):
        if not isinstance(x, torch.Tensor):
            raise TypeError("Input must be a torch.Tensor.")

        if x.dim() == 3:
            x = x.unsqueeze(0)

        if x.dim() != 4:
            raise ValueError(f"Expected IMAGE tensor [B,H,W,C], got shape {tuple(x.shape)}")

        return x

    def _ensure_rgb(self, image):
        c = image.shape[-1]

        if c == 1:
            image = image.repeat(1, 1, 1, 3)
        elif c >= 3:
            image = image[..., :3]
        else:
            raise ValueError(f"Unsupported channel count: {c}")

        return image

    def _match_batch(self, image, depth_map):
        bi = image.shape[0]
        bd = depth_map.shape[0]

        if bi == bd:
            return image, depth_map

        if bi == 1 and bd > 1:
            return image.repeat(bd, 1, 1, 1), depth_map

        if bd == 1 and bi > 1:
            return image, depth_map.repeat(bi, 1, 1, 1)

        raise ValueError(
            f"Batch mismatch: image batch={bi}, depth_map batch={bd}. "
            "Use matching batches, or one input with batch size 1."
        )

    def _prepare_depth(
        self,
        depth_map,
        target_h,
        target_w,
        invert,
        blur_kernel,
        gamma,
        contrast,
        near_clip,
        far_clip,
    ):
        depth = depth_map.permute(0, 3, 1, 2)

        if depth.shape[1] >= 3:
            r = depth[:, 0:1, :, :]
            g = depth[:, 1:2, :, :]
            b = depth[:, 2:3, :, :]
            depth = 0.299 * r + 0.587 * g + 0.114 * b
        else:
            depth = depth[:, 0:1, :, :]

        if depth.shape[-2] != target_h or depth.shape[-1] != target_w:
            depth = F.interpolate(
                depth,
                size=(target_h, target_w),
                mode="bilinear",
                align_corners=False,
            )

        batch_size = depth.shape[0]
        flat = depth.reshape(batch_size, -1)
        d_min = flat.min(dim=1)[0].view(batch_size, 1, 1, 1)
        d_max = flat.max(dim=1)[0].view(batch_size, 1, 1, 1)
        depth = (depth - d_min) / (d_max - d_min + 1e-8)
        depth = depth.clamp(0.0, 1.0)

        if invert:
            depth = 1.0 - depth

        near_clip = float(near_clip)
        far_clip = float(far_clip)

        if far_clip <= near_clip:
            near_clip = 0.0
            far_clip = 1.0

        depth = (depth - near_clip) / (far_clip - near_clip + 1e-8)
        depth = depth.clamp(0.0, 1.0)

        depth = ((depth - 0.5) * float(contrast)) + 0.5
        depth = depth.clamp(0.0, 1.0)

        depth = torch.pow(depth.clamp(0.0, 1.0), float(gamma))

        if int(blur_kernel) > 0:
            depth = self._gaussian_blur(depth, int(blur_kernel))

        return depth.clamp(0.0, 1.0)

    def _gaussian_blur(self, x, kernel_size):
        if kernel_size <= 1:
            return x

        if kernel_size % 2 == 0:
            kernel_size += 1

        sigma = max(kernel_size / 6.0, 1e-6)
        radius = kernel_size // 2

        coords = torch.arange(
            -radius,
            radius + 1,
            device=x.device,
            dtype=x.dtype,
        )

        kernel_1d = torch.exp(-(coords ** 2) / (2 * sigma ** 2))
        kernel_1d = kernel_1d / kernel_1d.sum()

        kernel_h = kernel_1d.view(1, 1, 1, kernel_size)
        kernel_v = kernel_1d.view(1, 1, kernel_size, 1)

        channels = x.shape[1]

        kernel_h = kernel_h.repeat(channels, 1, 1, 1)
        kernel_v = kernel_v.repeat(channels, 1, 1, 1)

        if x.shape[-1] > radius and x.shape[-2] > radius:
            x = F.pad(x, (radius, radius, 0, 0), mode="reflect")
            x = F.conv2d(x, kernel_h, groups=channels)

            x = F.pad(x, (0, 0, radius, radius), mode="reflect")
            x = F.conv2d(x, kernel_v, groups=channels)
        else:
            x = F.avg_pool2d(x, kernel_size=3, stride=1, padding=1)

        return x

    def _warp_horizontal(self, image, shift_px, padding_mode, interpolation):
        batch_size, h, w, _ = image.shape
        device = image.device
        dtype = image.dtype

        img = image.permute(0, 3, 1, 2)

        y = torch.linspace(-1.0, 1.0, h, device=device, dtype=dtype)
        x = torch.linspace(-1.0, 1.0, w, device=device, dtype=dtype)

        yy, xx = torch.meshgrid(y, x, indexing="ij")
        base_grid = torch.stack((xx, yy), dim=-1)
        base_grid = base_grid.unsqueeze(0).repeat(batch_size, 1, 1, 1)

        shift_norm = (shift_px[:, 0, :, :] * 2.0) / max(w - 1, 1)
        grid = base_grid.clone()
        grid[..., 0] = grid[..., 0] - shift_norm

        warped = F.grid_sample(
            img,
            grid,
            mode=interpolation,
            padding_mode=padding_mode,
            align_corners=True,
        )

        return warped.permute(0, 2, 3, 1).clamp(0.0, 1.0)

    def _make_anaglyph(self, left, right, mode):
        if mode == "color_red_cyan":
            out = torch.zeros_like(left)
            out[..., 0] = left[..., 0]
            out[..., 1] = right[..., 1]
            out[..., 2] = right[..., 2]
            return out

        if mode == "half_color_red_cyan":
            left_luma = self._luma(left)
            out = torch.zeros_like(left)
            out[..., 0] = left_luma[..., 0]
            out[..., 1] = right[..., 1]
            out[..., 2] = right[..., 2]
            return out

        if mode == "gray_red_cyan":
            left_luma = self._luma(left)
            right_luma = self._luma(right)
            out = torch.zeros_like(left)
            out[..., 0] = left_luma[..., 0]
            out[..., 1] = right_luma[..., 0]
            out[..., 2] = right_luma[..., 0]
            return out

        if mode == "optimized_dubois_red_cyan":
            return self._dubois_red_cyan(left, right)

        if mode == "color_red_blue":
            out = torch.zeros_like(left)
            out[..., 0] = left[..., 0]
            out[..., 1] = 0.0
            out[..., 2] = right[..., 2]
            return out

        if mode == "half_color_red_blue":
            left_luma = self._luma(left)
            out = torch.zeros_like(left)
            out[..., 0] = left_luma[..., 0]
            out[..., 1] = 0.0
            out[..., 2] = right[..., 2]
            return out

        if mode == "gray_red_blue":
            left_luma = self._luma(left)
            right_luma = self._luma(right)
            out = torch.zeros_like(left)
            out[..., 0] = left_luma[..., 0]
            out[..., 1] = 0.0
            out[..., 2] = right_luma[..., 0]
            return out

        out = torch.zeros_like(left)
        out[..., 0] = left[..., 0]
        out[..., 1] = right[..., 1]
        out[..., 2] = right[..., 2]
        return out

    def _luma(self, image):
        r = image[..., 0:1]
        g = image[..., 1:2]
        b = image[..., 2:3]
        return 0.299 * r + 0.587 * g + 0.114 * b

    def _dubois_red_cyan(self, left, right):
        l = left
        r = right

        out_r = (
            0.437 * l[..., 0]
            + 0.449 * l[..., 1]
            + 0.164 * l[..., 2]
            - 0.011 * r[..., 0]
            - 0.032 * r[..., 1]
            - 0.007 * r[..., 2]
        )

        out_g = (
            -0.062 * l[..., 0]
            - 0.062 * l[..., 1]
            - 0.024 * l[..., 2]
            + 0.377 * r[..., 0]
            + 0.761 * r[..., 1]
            + 0.009 * r[..., 2]
        )

        out_b = (
            -0.048 * l[..., 0]
            - 0.050 * l[..., 1]
            - 0.017 * l[..., 2]
            - 0.026 * r[..., 0]
            - 0.093 * r[..., 1]
            + 1.234 * r[..., 2]
        )

        out = torch.stack((out_r, out_g, out_b), dim=-1)
        return out.clamp(0.0, 1.0)


NODE_CLASS_MAPPINGS = {
    "Orion4D_DepthAnaglyph": Orion4D_DepthAnaglyph,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "Orion4D_DepthAnaglyph": "Orion4D Depth Anaglyph",
}
