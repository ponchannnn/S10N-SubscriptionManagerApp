"""下部タブの位置を保ち，画面の中身を左右にスライドする．"""
import asyncio

import flet as ft

import navigation

ANIMATION_MS = 280


class TabSlider:
    """同じStackを使い続け，タブの並び順に応じて遷移方向を変える．"""
    def __init__(self, page, route, content):
        self.page = page
        self.route = route
        self.generation = 0
        self.root = ft.Stack(expand=True, clip_behavior=ft.ClipBehavior.HARD_EDGE,
                             controls=[self._layer(content)])

    @staticmethod
    def _layer(content, offset=0):
        return ft.Container(content=content, left=0, top=0, right=0, bottom=0,
                            offset=ft.Offset(offset, 0))

    def show(self, route, content):
        self.generation += 1
        generation = self.generation
        if route == self.route:
            self.root.controls = [self._layer(content)]
            return self.root.controls[0]
        direction = 1 if navigation.TAB_ROUTES.index(route) > navigation.TAB_ROUTES.index(self.route) else -1
        self.route = route
        outgoing = self.root.controls[-1]
        outgoing.animate_offset = None
        outgoing.offset = ft.Offset(0, 0)
        incoming = self._layer(content, direction)
        self.root.controls = [outgoing, incoming]
        self.page.update()
        self.page.run_task(self._animate, outgoing, incoming, direction, generation)
        return incoming

    async def _animate(self, outgoing, incoming, direction, generation):
        # 初期位置を描画してから，次のフレームで移動を開始する．
        await asyncio.sleep(0.04)
        if generation != self.generation:
            return
        animation = ft.Animation(ANIMATION_MS, ft.AnimationCurve.EASE_OUT_CUBIC)
        outgoing.animate_offset = animation
        incoming.animate_offset = animation
        outgoing.offset = ft.Offset(-direction, 0)
        incoming.offset = ft.Offset(0, 0)
        self.page.update()
        await asyncio.sleep(ANIMATION_MS / 1000)
        if generation == self.generation:
            self.root.controls = [incoming]
            self.page.update()

    def cancel(self):
        """詳細・登録への移動やログアウト時に，古いアニメーションを無効化する．"""
        self.generation += 1
