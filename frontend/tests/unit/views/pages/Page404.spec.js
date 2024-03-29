import Vue from 'vue'
import regeneratorRuntime from "regenerator-runtime";
import { shallowMount } from '@vue/test-utils'
import CoreuiVue from '@coreui/vue'
import Page404 from '@/views/Page404'


Vue.use(regeneratorRuntime)
Vue.use(CoreuiVue)

describe('Page404.vue', () => {
  it('has a name', () => {
    expect(Page404.name).toBe('Page404')
  })
  it('is Vue instance', () => {
    const wrapper = shallowMount(Page404)
    expect(wrapper.vm).toBeTruthy()
  })
  it('is Page500', () => {
    const wrapper = shallowMount(Page404)
    expect(wrapper.findComponent(Page404)).toBeTruthy()
  })
  it('should render correct content', () => {
    const wrapper = shallowMount(Page404)
    expect(wrapper.find('h1').text()).toMatch('404')
  })
  test('renders correctly', () => {
    const wrapper = shallowMount(Page404)
    expect(wrapper.element).toMatchSnapshot()
  })
})
