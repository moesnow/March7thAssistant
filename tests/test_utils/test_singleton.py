from utils.singleton import SingletonMeta


class TestSingletonMeta:
    def test_same_instance(self):
        class MyClass(metaclass=SingletonMeta):
            pass

        a = MyClass()
        b = MyClass()
        assert a is b

    def test_different_classes(self):
        class ClassA(metaclass=SingletonMeta):
            pass

        class ClassB(metaclass=SingletonMeta):
            pass

        a = ClassA()
        b = ClassB()
        assert a is not b

    def test_constructor_args(self):
        class MyClass(metaclass=SingletonMeta):
            def __init__(self, value=None):
                self.value = value

        a = MyClass(42)
        b = MyClass(99)  # 第二次调用不会重新初始化
        assert a is b
        assert a.value == 42
